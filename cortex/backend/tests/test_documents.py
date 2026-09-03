from unittest.mock import patch, MagicMock


def fake_embedding_result(texts):
    mock_result = MagicMock()
    mock_result.embeddings = [[0.1] * 1024 for _ in texts]
    return mock_result


async def test_upload_document_creates_chunks(client):
    fake_file_content = b"This is a simple test document with some content in it."

    with patch("app.services.document_store.voyage_client.embed") as mock_embed:
        mock_embed.side_effect = lambda texts, **kwargs: fake_embedding_result(texts)

        response = await client.post(
            "/documents/",
            files={"file": ("test.txt", fake_file_content, "text/plain")},
        )

    assert response.status_code == 201
    data = response.json()
    assert data["filename"] == "test.txt"
    assert "id" in data

from sqlalchemy import select
from app.db.models import Chunk


async def test_delete_document_cascades_to_chunks(client, db_session):
    with patch("app.services.document_store.voyage_client.embed") as mock_embed:
        mock_embed.side_effect = lambda texts, **kwargs: fake_embedding_result(texts)

        create_response = await client.post(
            "/documents/",
            files={"file": ("cascade_test.txt", b"Some content to chunk and embed.", "text/plain")},
        )

    doc_id = create_response.json()["id"]

    delete_response = await client.delete(f"/documents/{doc_id}")
    assert delete_response.status_code == 204

    result = await db_session.execute(select(Chunk).where(Chunk.document_id == doc_id))
    remaining_chunks = result.scalars().all()
    assert len(remaining_chunks) == 0


async def test_list_documents_returns_all(client):
    with patch("app.services.document_store.voyage_client.embed") as mock_embed:
        mock_embed.side_effect = lambda texts, **kwargs: fake_embedding_result(texts)

        await client.post(
            "/documents/",
            files={"file": ("doc1.txt", b"First document content.", "text/plain")},
        )
        await client.post(
            "/documents/",
            files={"file": ("doc2.txt", b"Second document content.", "text/plain")},
        )

    response = await client.get("/documents/")
    assert response.status_code == 200

    data = response.json()
    filenames = [doc["filename"] for doc in data]
    assert "doc1.txt" in filenames
    assert "doc2.txt" in filenames


async def test_delete_nonexistent_document_returns_404(client):
    fake_id = "00000000-0000-0000-0000-000000000000"
    response = await client.delete(f"/documents/{fake_id}")
    assert response.status_code == 404


async def test_long_document_splits_into_multiple_chunks(client, db_session):
    long_text = ("This is a test sentence used to build up a long document. " * 50).encode()

    with patch("app.services.document_store.voyage_client.embed") as mock_embed:
        mock_embed.side_effect = lambda texts, **kwargs: fake_embedding_result(texts)

        response = await client.post(
            "/documents/",
            files={"file": ("long.txt", long_text, "text/plain")},
        )

    doc_id = response.json()["id"]

    result = await db_session.execute(select(Chunk).where(Chunk.document_id == doc_id))
    chunks = result.scalars().all()

    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk.content)  

async def test_chunks_have_overlapping_content(client, db_session):
    long_text_str = "".join("Sentence number %d about testing overlap behavior. " % i for i in range(100))
    long_text = long_text_str.encode()

    with patch("app.services.document_store.voyage_client.embed") as mock_embed:
        mock_embed.side_effect = lambda texts, **kwargs: fake_embedding_result(texts)

        response = await client.post(
            "/documents/",
            files={"file": ("overlap.txt", long_text, "text/plain")},
        )

    doc_id = response.json()["id"]

    result = await db_session.execute(select(Chunk).where(Chunk.document_id == doc_id))
    chunks = result.scalars().all()

    # Sort chunks by where their content actually starts in the original text
    chunks_in_order = sorted(chunks, key=lambda c: long_text_str.find(c.content))

    assert len(chunks_in_order) > 1
    end_of_first = chunks_in_order[0].content[-50:]
    assert end_of_first[:20] in chunks_in_order[1].content
async def test_empty_content_upload_handled_gracefully(client):
    empty_content = b""

    with patch("app.services.document_store.voyage_client.embed") as mock_embed:
        mock_embed.side_effect = lambda texts, **kwargs: fake_embedding_result(texts)

        response = await client.post(
            "/documents/",
            files={"file": ("empty.txt", empty_content, "text/plain")},
        )

    assert response.status_code in (400, 422)
async def test_all_chunks_have_embeddings(client, db_session):
    with patch("app.services.document_store.voyage_client.embed") as mock_embed:
        mock_embed.side_effect = lambda texts, **kwargs: fake_embedding_result(texts)

        response = await client.post(
            "/documents/",
            files={"file": ("embed_check.txt", b"Some content that will be embedded.", "text/plain")},
        )

    doc_id = response.json()["id"]

    result = await db_session.execute(select(Chunk).where(Chunk.document_id == doc_id))
    chunks = result.scalars().all()

    assert len(chunks) > 0
    for chunk in chunks:
        assert chunk.embedding is not None

from unittest.mock import patch, MagicMock
import uuid
from app.db.models import Document, Chunk
from app.services.document_store import DocumentStore


def fake_query_embedding_result(texts):
    mock_result = MagicMock()
    mock_result.embeddings = [[0.5] * 1024 for _ in texts]
    return mock_result


async def test_search_returns_chunks_ordered_by_similarity(db_session):
    doc = Document(filename="ranking_test.txt")
    db_session.add(doc)
    await db_session.flush()

    close_vector = [0.5] * 1024
    far_vector = [-0.5] * 1024
    medium_vector = [0.1] * 1024

    chunks = [
        Chunk(document_id=doc.id, content="far chunk", embedding=far_vector),
        Chunk(document_id=doc.id, content="close chunk", embedding=close_vector),
        Chunk(document_id=doc.id, content="medium chunk", embedding=medium_vector),
    ]
    db_session.add_all(chunks)
    await db_session.commit()

    store = DocumentStore()

    with patch("app.services.document_store.voyage_client.embed") as mock_embed:
        mock_embed.side_effect = lambda texts, **kwargs: fake_query_embedding_result(texts)

        results = await store.search_similar_chunks(db_session, "some question", top_k=3)

    contents_in_order = [chunk.content for chunk in results]
    assert contents_in_order == ["close chunk", "medium chunk", "far chunk"]


async def test_search_respects_top_k(db_session):
    doc = Document(filename="topk_test.txt")
    db_session.add(doc)
    await db_session.flush()

    chunks = [
        Chunk(document_id=doc.id, content=f"chunk {i}", embedding=[0.1 * i] * 1024)
        for i in range(10)
    ]
    db_session.add_all(chunks)
    await db_session.commit()

    store = DocumentStore()

    with patch("app.services.document_store.voyage_client.embed") as mock_embed:
        mock_embed.side_effect = lambda texts, **kwargs: fake_query_embedding_result(texts)

        results = await store.search_similar_chunks(db_session, "some question", top_k=3)

    assert len(results) == 3

async def test_search_with_empty_question_handled(db_session):
    store = DocumentStore()

    with patch("app.services.document_store.voyage_client.embed") as mock_embed:
        mock_embed.side_effect = lambda texts, **kwargs: fake_query_embedding_result(texts)

        response = await store.search_similar_chunks(db_session, "", top_k=5)
def fake_gemini_response(text):
    mock_response = MagicMock()
    mock_response.text = text
    return mock_response


async def test_generate_answer_response_shape(db_session):
    doc = Document(filename="gen_test.txt")
    db_session.add(doc)
    await db_session.flush()

    chunk = Chunk(document_id=doc.id, content="Paris is the capital of France.", embedding=[0.5] * 1024)
    db_session.add(chunk)
    await db_session.commit()

    store = DocumentStore()

    with patch("app.services.document_store.voyage_client.embed") as mock_embed, \
         patch("app.services.document_store.gemini_client.models.generate_content") as mock_generate:

        mock_embed.side_effect = lambda texts, **kwargs: fake_query_embedding_result(texts)
        mock_generate.return_value = fake_gemini_response("Paris is the capital of France.")

        result = await store.generate_answer(db_session, "What is the capital of France?", top_k=5)

    assert "answer" in result
    assert "sources" in result
    assert result["answer"] == "Paris is the capital of France."
    assert isinstance(result["sources"], list)

async def test_grounded_prompt_includes_chunk_content(db_session):
    doc = Document(filename="prompt_test.txt")
    db_session.add(doc)
    await db_session.flush()

    chunk = Chunk(document_id=doc.id, content="The sky appears blue due to Rayleigh scattering.", embedding=[0.5] * 1024)
    db_session.add(chunk)
    await db_session.commit()

    store = DocumentStore()

    with patch("app.services.document_store.voyage_client.embed") as mock_embed, \
         patch("app.services.document_store.gemini_client.models.generate_content") as mock_generate:

        mock_embed.side_effect = lambda texts, **kwargs: fake_query_embedding_result(texts)
        mock_generate.return_value = fake_gemini_response("Some answer")

        await store.generate_answer(db_session, "Why is the sky blue?", top_k=5)

    call_args = mock_generate.call_args
    sent_prompt = call_args.kwargs["contents"]
    assert "Rayleigh scattering" in sent_prompt

async def test_no_relevant_chunks_does_not_hallucinate(db_session):
    store = DocumentStore()

    with patch("app.services.document_store.voyage_client.embed") as mock_embed, \
         patch("app.services.document_store.gemini_client.models.generate_content") as mock_generate:

        mock_embed.side_effect = lambda texts, **kwargs: fake_query_embedding_result(texts)
        mock_generate.return_value = fake_gemini_response("I don't have enough information to answer that.")

        result = await store.generate_answer(db_session, "What is quantum entanglement?", top_k=5)

    mock_generate.assert_called_once()
    assert result["sources"] == []