import streamlit as st
import pandas as pd
import chromadb
import os

st.set_page_config(page_title="ChromaDB Explorer", layout="wide")
st.title("🗄️ ChromaDB Local Explorer")

@st.cache_resource
def get_client():
    db_path = r"C:\Users\ranug\Clario\clario\clario-ml-sidecar\vector_store\chroma_data"
    return chromadb.PersistentClient(path=db_path)

client = get_client()
collections = client.list_collections()

if not collections:
    st.warning("No collections found in this database.")
else:
    col_names = [c.name for c in collections]
    selected_col = st.sidebar.selectbox("Select Collection", col_names)
    
    collection = client.get_collection(selected_col)
    count = collection.count()
    
    st.sidebar.metric("Total Documents", count)
    
    st.subheader(f"Collection: {selected_col}")
    
    if count > 0:
        # Fetch up to 100 docs for viewing
        limit = min(count, 100)
        data = collection.peek(limit)
        
        docs = data.get("documents", [])
        metas = data.get("metadatas", [])
        ids = data.get("ids", [])
        
        # Build dataframe
        df_data = []
        for i in range(len(docs)):
            row = {"ID": ids[i], "Document": docs[i]}
            if metas and metas[i]:
                for k, v in metas[i].items():
                    row[f"meta_{k}"] = v
            df_data.append(row)
            
        df = pd.DataFrame(df_data)
        st.dataframe(df, use_container_width=True)
    else:
        st.info("Collection is empty.")
