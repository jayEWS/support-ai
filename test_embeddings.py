try:
    from langchain_huggingface import HuggingFaceEmbeddings
    print("Trying to init HuggingFaceEmbeddings...")
    embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    print("Success!")
except Exception as e:
    print(f"Failed: {e}")
    import traceback
    traceback.print_exc()
