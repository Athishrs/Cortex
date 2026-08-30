from langchain_text_splitters import RecursiveCharacterTextSplitter

sample_text = """
Employee Vacation Policy

All full-time employees receive 15 days of paid vacation per year. Vacation days accrue monthly and can be carried over up to 5 days into the next calendar year.

To request time off, employees must submit a request through the HR portal at least two weeks in advance. Manager approval is required for requests longer than 5 consecutive days.

Sick Leave Policy

Employees receive 10 days of paid sick leave annually. Unused sick leave does not carry over to the next year and cannot be cashed out upon termination.
"""

splitter = RecursiveCharacterTextSplitter(
    chunk_size=200,
    chunk_overlap=40,
)

chunks = splitter.split_text(sample_text)

for i, chunk in enumerate(chunks):
    print(f"--- Chunk {i} ({len(chunk)} chars) ---")
    print(chunk)
    print()