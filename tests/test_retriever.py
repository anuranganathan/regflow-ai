from app.rag.retriever import get_retriever


def test_knowledge_base_is_loaded():
    sources = {chunk.source for chunk in get_retriever().chunks}
    assert sources == {
        "gst_registration.txt", "gst_rates.txt", "gst_input_tax_credit.txt",
        "gst_invoice_rules.txt", "gst_return_rules.txt",
    }


def test_retrieves_relevant_rules():
    retriever = get_retriever()

    top = retriever.retrieve("mandatory fields on a tax invoice hsn code", top_k=3)
    assert top[0].source == "gst_invoice_rules.txt"

    top = retriever.retrieve("claim input tax credit within 180 days", top_k=3)
    assert top[0].source == "gst_input_tax_credit.txt"

    top = retriever.retrieve("GSTR-3B table 3.1(a) due date", top_k=3)
    assert top[0].source == "gst_return_rules.txt"


def test_unrelated_query_returns_nothing():
    assert get_retriever().retrieve("football weather banana") == []
