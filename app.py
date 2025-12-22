import streamlit as st
import requests
import os
import time
import json
from dotenv import load_dotenv

load_dotenv()

# Try to get from Streamlit secrets (for cloud deployment)
try:
    API_KEY = st.secrets["API_KEY"]
    API_URL = st.secrets.get("RAG_API_URL", "https://rag-genai-api-t6kt2462uq-uc.a.run.app")
except (FileNotFoundError, KeyError):
    from dotenv import load_dotenv
    import os
    load_dotenv()
    API_KEY = os.getenv("RAG_API_KEY", "dummy-key-for-local-dev-only") # Fallback for local dev
    API_URL = os.getenv("RAG_API_URL", "https://rag-genai-api-t6kt2462uq-uc.a.run.app")
    


# ========== INITIALIZE SESSION STATES ==========
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []

if 'uploaded_documents' not in st.session_state:
    st.session_state.uploaded_documents = []

if 'feedback' not in st.session_state:
    st.session_state.feedback = {}

if 'auto_fill_question' not in st.session_state:
    st.session_state.auto_fill_question = None

if 'switch_to_chat' not in st.session_state:
    st.session_state.switch_to_chat = False

if 'chat_with_doc' not in st.session_state:
    st.session_state.chat_with_doc = None

if 'selected_document' not in st.session_state:
    st.session_state.selected_document = None

# Page setup
st.set_page_config(
    page_title="RAG Document Assistant",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("📚 RAG Document Assistant")
st.markdown("Upload PDFs and ask questions about their content using AI.")

# ========== HELPER FUNCTIONS ==========
def test_api_connection():
    """Test if the RAG API is reachable"""
    try:
        headers = {"X-API-Key": API_KEY}
        response = requests.get(f"{API_URL}/health", headers=headers, timeout=5)
        if response.status_code == 200:
            return True, response.json()
        else:
            return False, {"error": f"API returned status {response.status_code}"}
    except Exception as e:
        return False, {"error": str(e)}

def get_system_status():
    """Get detailed system status"""
    try:
        headers = {"X-API-Key": API_KEY}
        health_response = requests.get(f"{API_URL}/health", headers=headers, timeout=5)
        
        # Try to get document count if endpoint exists
        doc_count = "Check upload tab"
        try:
            docs_response = requests.get(f"{API_URL}/documents", headers=headers, timeout=5)
            if docs_response.status_code == 200:
                docs_data = docs_response.json()
                doc_count = len(docs_data.get('documents', []))
        except:
            pass
        
        return {
            "api_status": "✅ Online" if health_response.status_code == 200 else "❌ Offline",
            "documents_loaded": doc_count,
            "endpoint": API_URL
        }
    except Exception as e:
        return {
            "api_status": "❌ Error",
            "error": str(e),
            "endpoint": API_URL
        }

def get_upload_endpoint():
    """Determine the correct upload endpoint"""
    base_url = API_URL.rstrip('/')
    return f"{base_url}/upload"

def add_feedback_to_history(question_idx, feedback_type):
    """Store user feedback for response quality"""
    st.session_state.feedback[question_idx] = {
        'type': feedback_type,
        'timestamp': time.strftime("%Y-%m-%d %H:%M:%S")
    }
    
    # Show toast notification
    if feedback_type == 'good':
        st.toast("👍 Thanks for the positive feedback!", icon="👍")
    else:
        st.toast("👎 Thanks for the feedback. We'll improve!", icon="👎")

# ========== GLOBAL CHAT INPUT ==========
question = st.chat_input("Enter your question here...")

# ========== SIDEBAR ==========
with st.sidebar:
    st.header("🔌 Connection & Status")
    
    # Status display
    if st.button("🔄 Check System Status", use_container_width=True, type="secondary"):
        status = get_system_status()
        st.json(status)
    
    if st.button("🔗 Test API Connection", use_container_width=True):
        with st.spinner("Testing connection..."):
            connected, info = test_api_connection()
            if connected:
                st.success("✅ Connected to RAG API")
                st.json(info)
            else:
                st.error("❌ Connection failed")
                st.error(info.get("error", "Unknown error"))
    
    st.divider()
    st.header("💾 Chat Management")
    
    # Clear chat button
    if st.button("🗑️ Clear Chat History", use_container_width=True):
        st.session_state.chat_history = []
        st.session_state.feedback = {}
        st.success("Chat history cleared!")
        time.sleep(0.5)
        st.rerun()
    
    # Export chat button
    if st.session_state.chat_history:
        if st.button("📥 Export Chat as JSON", use_container_width=True):
            # Prepare export data
            export_data = {
                "chat_history": st.session_state.chat_history,
                "feedback": st.session_state.feedback,
                "metadata": {
                    "export_date": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "total_conversations": len(st.session_state.chat_history),
                    "total_messages": len(st.session_state.chat_history) * 2
                }
            }
            
            # Create download button
            json_str = json.dumps(export_data, indent=2)
            st.download_button(
                label="💾 Download JSON File",
                data=json_str,
                file_name=f"chat_export_{time.strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json",
                use_container_width=True
            )
    
    # Show chat stats
    if st.session_state.chat_history:
        st.info(f"💬 {len(st.session_state.chat_history)} conversations")
        if st.session_state.feedback:
            good_feedback = sum(1 for f in st.session_state.feedback.values() if f['type'] == 'good')
            st.caption(f"👍 {good_feedback} positive feedback")
    
    st.divider()
    st.header("📊 Quick Stats")
    
    col_stat1, col_stat2 = st.columns(2)
    with col_stat1:
        st.metric("Documents", len(st.session_state.uploaded_documents))
    with col_stat2:
        st.metric("Chats", len(st.session_state.chat_history))
    
    if st.session_state.uploaded_documents:
        total_chunks = sum(d.get('chunks', 0) for d in st.session_state.uploaded_documents)
        st.metric("Total Chunks", total_chunks)
    
    st.divider()
    st.header("⚙️ Settings")
    
    # Endpoint configuration
    with st.expander("API Endpoint", expanded=False):
        current_endpoint = st.text_input("Upload Endpoint", value=get_upload_endpoint())
        st.caption("Change if your API uses a different endpoint")
    
    st.divider()
    st.header("ℹ️ About")
    st.write("This interface connects to your RAG API at:")
    st.code(API_URL)
    st.caption("v2.1 • Enhanced with document selection & filtering")

# ========== MAIN TABS ==========
tab1, tab2, tab3 = st.tabs(["💬 Chat", "📤 Upload & Manage", "📊 Analytics"])

# ========== TAB 1: CHAT INTERFACE WITH DOCUMENT SELECTION ==========
with tab1:
    # Handle document-specific chat switching
    if st.session_state.switch_to_chat:
        st.info(f"💬 Now chatting about: **{st.session_state.chat_with_doc}**")
        if st.button("Clear document focus"):
            st.session_state.switch_to_chat = False
            st.session_state.chat_with_doc = None
            st.rerun()
    
    # Handle auto-fill questions
    if st.session_state.auto_fill_question:
        st.info(f"💡 **Suggested question:** `{st.session_state.auto_fill_question}`")
        
        col_use, col_cancel = st.columns([3, 1])
        with col_use:
            if st.button(f"🔍 Use this question", use_container_width=True):
                st.session_state.pending_question = st.session_state.auto_fill_question
                del st.session_state.auto_fill_question
                st.rerun()
        with col_cancel:
            if st.button("Cancel", use_container_width=True):
                del st.session_state.auto_fill_question
                st.rerun()
    
    st.header("Ask Questions")
    
    # ========== DOCUMENT SELECTION UI ==========
    if st.session_state.uploaded_documents:
        # Create document options
        doc_options = ["🔍 Search All Documents"] + [f"📄 {doc['name']}" for doc in st.session_state.uploaded_documents]
        
        selected_doc_display = st.selectbox(
            "📄 Select document to query:",
            doc_options,
            index=0,
            help="Choose a specific document or search all uploaded documents"
        )
        
        # Extract the actual document name
        if selected_doc_display == "🔍 Search All Documents":
            selected_doc_name = None
            selected_doc_id = None
            st.info("🔍 Will search across **all uploaded documents**")
        else:
            # Remove the emoji prefix
            selected_doc_name = selected_doc_display.replace("📄 ", "")
            # Find the document info
            selected_doc_info = None
            for doc in st.session_state.uploaded_documents:
                if doc['name'] == selected_doc_name:
                    selected_doc_info = doc
                    break
            
            if selected_doc_info:
                st.success(f"✅ Will search in: **{selected_doc_name}**")
                st.caption(f"📊 {selected_doc_info.get('chunks', 0)} chunks • {selected_doc_info.get('size_mb', 0):.2f} MB")
                st.session_state.selected_document = {
                    'name': selected_doc_name,
                    'id': selected_doc_info.get('document_id', selected_doc_name),
                    'info': selected_doc_info
                }
            else:
                st.warning(f"Document '{selected_doc_name}' not found in uploaded documents")
                st.session_state.selected_document = None
    else:
        st.warning("⚠️ No documents uploaded yet. Go to the **Upload & Manage** tab first.")
        st.session_state.selected_document = None
    
    st.divider()
    
    # ========== CHAT HISTORY DISPLAY ==========
    for i, chat in enumerate(st.session_state.chat_history):
        # Show which document was searched (if specified)
        if chat.get('document_searched'):
            st.caption(f"📄 Searched in: {chat['document_searched']}")
        
        # User message
        with st.chat_message("user"):
            st.write(chat['question'])
        
        # Assistant message
        with st.chat_message("assistant"):
            st.write(chat['answer'])
            
            # Show sources if available
            if chat.get('sources') and len(chat['sources']) > 0:
                with st.expander(f"📚 View sources ({len(chat['sources'])})"):
                    for j, source in enumerate(chat['sources']):
                        st.markdown(f"**Source {j+1}:**")
                        if source.get('content'):
                            content = source['content']
                            display_text = content[:300] + "..." if len(content) > 300 else content
                            st.write(display_text)
            
            # Feedback buttons
            col_fb1, col_fb2, col_fb3 = st.columns([1, 1, 8])
            with col_fb1:
                if st.button("👍", key=f"good_{i}", help="Good response"):
                    add_feedback_to_history(i, 'good')
            with col_fb2:
                if st.button("👎", key=f"bad_{i}", help="Poor response"):
                    add_feedback_to_history(i, 'bad')
            with col_fb3:
                # Show feedback status if given
                if i in st.session_state.feedback:
                    fb_type = st.session_state.feedback[i]['type']
                    st.caption(f"You marked this as {fb_type}")
    
    # ========== PROCESS INCOMING QUESTIONS ==========
    if question:
        # Display user message
        with st.chat_message("user"):
            st.write(question)
        
        with st.spinner("Searching documents..."):
            try:
                # Prepare query parameters
                params = {"question": question}
                
                # Add document filter if selected
                selected_doc = st.session_state.get('selected_document')
                if selected_doc:
                    doc_name = selected_doc['name']
                    params["document_name"] = doc_name
                    params["document_filter"] = doc_name
                    
                    if selected_doc.get('id'):
                        params["document_id"] = selected_doc['id']
                    
                    st.info(f"🔍 Searching in: **{doc_name}**")
                elif st.session_state.uploaded_documents:
                    st.info("🔍 Searching across **all uploaded documents**")
                
                # Check if we're in document-specific chat mode
                if st.session_state.chat_with_doc:
                    params["document_filter"] = st.session_state.chat_with_doc
                    params["document_name"] = st.session_state.chat_with_doc
                
                # Call the RAG API with authentication
                headers = {"X-API-Key": API_KEY}
                response = requests.post(f"{API_URL}/query", params=params, headers=headers, timeout=30)
                
                if response.status_code == 200:
                    result = response.json()
                    answer = result.get("answer", "No answer provided")
                    
                    # Display assistant message
                    with st.chat_message("assistant"):
                        st.write(answer)
                        
                        # Indicate which document was searched
                        searched_doc = None
                        if selected_doc:
                            searched_doc = selected_doc['name']
                        elif st.session_state.chat_with_doc:
                            searched_doc = st.session_state.chat_with_doc
                        
                        if searched_doc:
                            st.caption(f"📄 Searched in: {searched_doc}")
                        elif st.session_state.uploaded_documents:
                            st.caption("🔍 Searched across all documents")
                    
                    # Store in chat history
                    st.session_state.chat_history.append({
                        'question': question,
                        'answer': answer,
                        'sources': result.get('sources', []),
                        'timestamp': time.strftime("%Y-%m-%d %H:%M:%S"),
                        'document_searched': searched_doc or "All Documents",
                        'query_params': params
                    })
                    
                else:
                    with st.chat_message("assistant"):
                        st.error(f"API Error: {response.status_code}")
                        if response.text:
                            st.error(f"Details: {response.text[:200]}")
                    
                    st.session_state.chat_history.append({
                        'question': question,
                        'answer': f"Error: API returned {response.status_code}",
                        'sources': [],
                        'error': True,
                        'timestamp': time.strftime("%Y-%m-%d %H:%M:%S")
                    })
                        
            except Exception as e:
                with st.chat_message("assistant"):
                    st.error(f"Error: {e}")
                st.session_state.chat_history.append({
                    'question': question,
                    'answer': f"Error: {str(e)}",
                    'sources': [],
                    'error': True,
                    'timestamp': time.strftime("%Y-%m-%d %H:%M:%S")
                })
    
    # Welcome message for empty state
    if not st.session_state.chat_history and not question:
        st.info("""
        👋 **Welcome to RAG Document Assistant!**
        
        **To get started:**
        1. Upload PDF documents in the **Upload & Manage** tab
        2. **Select a document** to query from the dropdown above
        3. Ask questions about your documents here
        4. Try the example questions below for inspiration
        """)

# ========== TAB 2: UPLOAD & MANAGE ==========
with tab2:
    st.header("📤 Upload & Manage Documents")
    
    col_upload, col_manage = st.columns([3, 2])
    
    with col_upload:
        st.subheader("Upload New Document")
        
        uploaded_file = st.file_uploader(
            "Choose a PDF file", 
            type="pdf",
            help="Select a PDF document to upload and process"
        )
        
        if uploaded_file:
            file_size_mb = uploaded_file.size / (1024 * 1024)
            
            st.info(f"""
            **File Selected:** {uploaded_file.name}
            **Size:** {file_size_mb:.2f} MB
            **Type:** PDF
            """)
            
            # Advanced settings
            with st.expander("⚙️ Processing Settings", expanded=False):
                col_size, col_overlap = st.columns(2)
                
                with col_size:
                    chunk_size = st.slider(
                        "Chunk Size",
                        min_value=500,
                        max_value=2000,
                        value=1000,
                        step=100
                    )
                
                with col_overlap:
                    chunk_overlap = st.slider(
                        "Chunk Overlap",
                        min_value=0,
                        max_value=500,
                        value=200,
                        step=50
                    )
                
                process_name = st.text_input(
                    "Document Name",
                    value=uploaded_file.name.replace('.pdf', ''),
                    help="Custom name for this document"
                )
            
            # Upload button
            if st.button("🚀 Upload & Process", type="primary", use_container_width=True):
                with st.spinner("Uploading..."):
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    try:
                        # Get upload endpoint
                        upload_endpoint = get_upload_endpoint()
                        
                        # Prepare upload
                        status_text.text("📤 Uploading file...")
                        progress_bar.progress(30)
                        
                        files = {"file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
                        data = {
                            "chunk_size": chunk_size,
                            "chunk_overlap": chunk_overlap,
                            "document_name": process_name
                        }
                        
                        # Send to API with authentication
                        status_text.text("⚙️ Processing...")
                        progress_bar.progress(60)
                        
                        headers = {"X-API-Key": API_KEY}
                        response = requests.post(upload_endpoint, files=files, data=data, headers=headers, timeout=180)
                        
                        # Handle response
                        progress_bar.progress(90)
                        
                        if response.status_code == 200:
                            result = response.json()
                            
                            # Try to extract document ID from response
                            document_id = result.get('document_id') or result.get('id') or result.get('file_id')
                            
                            # If no ID in response, create one
                            if not document_id:
                                document_id = f"doc_{int(time.time())}_{uploaded_file.name[:20]}"
                            
                            # Add to uploaded documents
                            doc_info = {
                                'name': process_name or uploaded_file.name,
                                'original_filename': uploaded_file.name,
                                'size_mb': file_size_mb,
                                'chunks': result.get('chunks_added', 0),
                                'chunk_size': chunk_size,
                                'chunk_overlap': chunk_overlap,
                                'timestamp': time.strftime("%Y-%m-%d %H:%M:%S"),
                                'status': '✅ Processed',
                                'document_id': document_id,
                                'upload_response': result
                            }
                            
                            st.session_state.uploaded_documents.append(doc_info)
                            
                            progress_bar.progress(100)
                            status_text.text("✅ Success!")
                            
                            st.success(f"**{uploaded_file.name}** uploaded successfully!")
                            st.balloons()
                            
                            # Show metrics
                            col1, col2, col3 = st.columns(3)
                            with col1:
                                st.metric("Chunks", result.get('chunks_added', 0))
                            with col2:
                                st.metric("Size", f"{file_size_mb:.2f} MB")
                            with col3:
                                st.metric("Status", "✅")
                            
                            # Show document ID for debugging
                            with st.expander("🔍 Document Details", expanded=False):
                                st.write(f"**Document ID:** {document_id}")
                                st.json(result)
                            
                        else:
                            progress_bar.progress(100)
                            status_text.text("❌ Failed")
                            st.error(f"Upload failed: {response.status_code}")
                            
                    except requests.exceptions.Timeout:
                        progress_bar.progress(100)
                        status_text.text("⏱️ Timeout")
                        st.error("Upload timed out after 3 minutes. Try a smaller file.")
                        
                    except Exception as e:
                        progress_bar.progress(100)
                        status_text.text("❌ Error")
                        st.error(f"Upload failed: {str(e)}")
        
        else:
            st.info("👆 Select a PDF file to upload")
    
    with col_manage:
        st.subheader("📋 Document Management")
        
        if st.session_state.uploaded_documents:
            # Search functionality
            search_term = st.text_input("🔍 Search documents", placeholder="Type to filter...")
            
            filtered_docs = st.session_state.uploaded_documents
            if search_term:
                filtered_docs = [d for d in filtered_docs if search_term.lower() in d['name'].lower()]
            
            st.write(f"**Showing {len(filtered_docs)} of {len(st.session_state.uploaded_documents)} documents**")
            
            # Display documents
            for i, doc in enumerate(filtered_docs):
                with st.expander(f"📄 {doc['name']}", expanded=False):
                    # Document info
                    col_info1, col_info2 = st.columns(2)
                    with col_info1:
                        st.metric("Chunks", doc.get('chunks', 0))
                        st.caption(f"Size: {doc.get('size_mb', 0):.2f} MB")
                    with col_info2:
                        st.metric("Status", doc.get('status', 'Unknown'))
                        st.caption(f"Added: {doc.get('timestamp', 'Unknown')}")
                    
                    # Show document ID if available
                    if doc.get('document_id'):
                        st.caption(f"**Document ID:** `{doc['document_id']}`")
                    
                    # Actions
                    st.subheader("Actions")
                    action_cols = st.columns(2)
                    
                    with action_cols[0]:
                        if st.button("💬 Chat with this", key=f"chat_{i}", use_container_width=True):
                            st.session_state.switch_to_chat = True
                            st.session_state.chat_with_doc = doc['name']
                            st.session_state.selected_document = {
                                'name': doc['name'],
                                'id': doc.get('document_id', doc['name'])
                            }
                            st.rerun()
                    
                    with action_cols[1]:
                        if st.button("🗑️ Remove", key=f"remove_{i}", use_container_width=True, type="secondary"):
                            if st.checkbox(f"Confirm delete {doc['name']}?", key=f"confirm_{i}"):
                                st.session_state.uploaded_documents.pop(i)
                                st.success(f"Removed {doc['name']}")
                                st.rerun()
            
            # Bulk operations
            st.divider()
            st.subheader("Bulk Operations")
            
            col_bulk1, col_bulk2 = st.columns(2)
            with col_bulk1:
                if st.button("📥 Export List", use_container_width=True):
                    export_data = {
                        "documents": st.session_state.uploaded_documents,
                        "export_date": time.strftime("%Y-%m-%d %H:%M:%S"),
                        "total_chunks": sum(d.get('chunks', 0) for d in st.session_state.uploaded_documents)
                    }
                    
                    st.download_button(
                        label="Download JSON",
                        data=json.dumps(export_data, indent=2),
                        file_name="documents_export.json",
                        mime="application/json",
                        use_container_width=True
                    )
            
            with col_bulk2:
                if st.button("🔄 Refresh", use_container_width=True):
                    st.info("Document list refreshed from session")
        
        else:
            st.info("📭 No documents uploaded yet")
            st.write("Upload your first PDF to get started!")

# ========== TAB 3: ANALYTICS ==========
with tab3:
    st.header("📊 Usage Analytics")
    
    if not st.session_state.chat_history and not st.session_state.uploaded_documents:
        st.info("No data yet. Start chatting and uploading to see analytics!")
    else:
        # Metrics dashboard
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            total_chats = len(st.session_state.chat_history)
            st.metric("Total Chats", total_chats)
        
        with col2:
            total_docs = len(st.session_state.uploaded_documents)
            st.metric("Documents", total_docs)
        
        with col3:
            total_chunks = sum(d.get('chunks', 0) for d in st.session_state.uploaded_documents)
            st.metric("Total Chunks", total_chunks)
        
        with col4:
            if st.session_state.chat_history:
                total_words = sum(len(str(chat.get('answer', '')).split()) for chat in st.session_state.chat_history)
                avg_words = total_words / len(st.session_state.chat_history) if st.session_state.chat_history else 0
                st.metric("Avg Response", f"{avg_words:.0f} words")
            else:
                st.metric("Avg Response", "N/A")
        
        st.divider()
        
        # Document usage analytics
        if st.session_state.uploaded_documents:
            st.subheader("📄 Document Usage")
            
            # Count queries per document
            doc_usage = {}
            for chat in st.session_state.chat_history:
                doc_name = chat.get('document_searched', 'All Documents')
                doc_usage[doc_name] = doc_usage.get(doc_name, 0) + 1
            
            # Display usage stats
            for doc_name, count in sorted(doc_usage.items(), key=lambda x: x[1], reverse=True):
                col_doc1, col_doc2 = st.columns([3, 1])
                with col_doc1:
                    st.write(f"**{doc_name}**")
                with col_doc2:
                    st.metric("Queries", count)
        
        # Recent activity
        st.divider()
        st.subheader("📈 Recent Activity")
        
        col_activity1, col_activity2 = st.columns(2)
        
        with col_activity1:
            st.subheader("💬 Recent Conversations")
            if st.session_state.chat_history:
                recent_chats = st.session_state.chat_history[-3:]
                for chat in reversed(recent_chats):
                    with st.expander(f"Q: {chat['question'][:50]}...", expanded=False):
                        st.write(f"**Question:** {chat['question']}")
                        st.write(f"**Answer:** {chat['answer'][:200]}...")
                        if chat.get('document_searched'):
                            st.caption(f"📄 Searched in: {chat['document_searched']}")
            else:
                st.info("No conversations yet")
        
        with col_activity2:
            st.subheader("📄 Recent Documents")
            if st.session_state.uploaded_documents:
                recent_docs = st.session_state.uploaded_documents[-3:]
                for doc in reversed(recent_docs):
                    with st.expander(f"{doc['name']}", expanded=False):
                        st.write(f"**Chunks:** {doc.get('chunks', 0)}")
                        st.write(f"**Size:** {doc.get('size_mb', 0):.2f} MB")
                        st.write(f"**Uploaded:** {doc.get('timestamp', 'Unknown')}")
                        if doc.get('document_id'):
                            st.caption(f"ID: {doc['document_id']}")
            else:
                st.info("No documents uploaded yet")
        
        # Feedback summary
        if st.session_state.feedback:
            st.divider()
            st.subheader("👍 Feedback Summary")
            
            good_feedback = sum(1 for f in st.session_state.feedback.values() if f['type'] == 'good')
            bad_feedback = sum(1 for f in st.session_state.feedback.values() if f['type'] == 'bad')
            total_feedback = len(st.session_state.feedback)
            
            col_fb1, col_fb2, col_fb3 = st.columns(3)
            with col_fb1:
                st.metric("Positive", good_feedback)
            with col_fb2:
                st.metric("Negative", bad_feedback)
            with col_fb3:
                if total_feedback > 0:
                    satisfaction = (good_feedback / total_feedback) * 100
                    st.metric("Satisfaction", f"{satisfaction:.0f}%")
                else:
                    st.metric("Satisfaction", "N/A")

# ========== EXAMPLE QUESTIONS ==========
st.divider()
st.subheader("🚀 Quick Actions & Examples")

# Categorized example questions
example_categories = {
    "📊 Analysis": [
        "What are the main findings?",
        "Summarize the key points",
        "What methodology was used?"
    ],
    "🔍 Details": [
        "List all recommendations",
        "What data sources were referenced?",
        "What metrics are mentioned?"
    ],
    "💡 Insights": [
        "What are the conclusions?",
        "Explain the main arguments",
        "What limitations are discussed?"
    ]
}

# Display categories
for category, questions in example_categories.items():
    with st.expander(category, expanded=True):
        cols = st.columns(3)
        for idx, question in enumerate(questions):
            with cols[idx]:
                if st.button(
                    question,
                    key=f"cat_{category[:5]}_{idx}",
                    use_container_width=True,
                    help=f"Click to use this question"
                ):
                    st.session_state.auto_fill_question = question
                    st.rerun()

# Footer
st.divider()
st.caption("RAG Document Assistant v2.1 • Enhanced with document selection & filtering")

# ========== DEBUG SECTION (Collapsed by default) ==========
with st.expander("🔧 Debug Information", expanded=False):
    st.write("**Session State:**")
    st.json({
        "chat_history_count": len(st.session_state.chat_history),
        "uploaded_documents_count": len(st.session_state.uploaded_documents),
        "selected_document": st.session_state.selected_document,
        "chat_with_doc": st.session_state.chat_with_doc
    })
    
    st.write("**API Endpoints:**")
    st.code(f"""
    Health: {API_URL}/health
    Upload: {get_upload_endpoint()}
    Query: {API_URL}/query
    """)
    
    # Test API endpoints
    if st.button("🧪 Test All Endpoints"):
        endpoints = {
            "Health": f"{API_URL}/health",
            "Upload": get_upload_endpoint(),
            "Query": f"{API_URL}/query?question=test"
        }
        
        for name, url in endpoints.items():
            try:
                headers = {"X-API-Key": API_KEY}
                if "query" in url:
                    response = requests.post(url, headers=headers, timeout=5)
                else:
                    response = requests.get(url, headers=headers, timeout=5)
                st.write(f"{name}: {'✅' if response.status_code < 400 else '❌'} {response.status_code}")
            except:
                st.write(f"{name}: ❌ Failed")