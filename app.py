import os  
import streamlit as st  
import openai  
import time  
from collections import defaultdict  
  
# Azure OpenAIの設定（環境変数から取得）  
AZURE_OPENAI_KEY = os.getenv("AZURE_OPENAI_KEY")  
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")  
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")  
ASSISTANT_ID = os.getenv("AZURE_OPENAI_ASSISTANT_ID")  # Code Interpreter有効なassistant_id  
  
client = openai.AzureOpenAI(  
    api_key=AZURE_OPENAI_KEY,  
    azure_endpoint=AZURE_OPENAI_ENDPOINT,  
    api_version=AZURE_OPENAI_API_VERSION  
)  
  
st.set_page_config(page_title="ファイル分析AIチャット", layout="wide")  
st.title("ファイル分析AIチャット（Azure OpenAI Assistants API + Code Interpreter）")  
  
if "thread_id" not in st.session_state:  
    st.session_state.thread_id = None  
if "messages" not in st.session_state:  
    st.session_state.messages = []  
if "selected_analysis_file_id" not in st.session_state:  
    st.session_state.selected_analysis_file_id = None  
  
# サポートされている拡張子  
supported_types = [  
    "c", "cs", "cpp", "doc", "docx", "html", "java", "json", "md", "pdf", "php", "pptx",  
    "py", "rb", "tex", "txt", "css", "js", "sh", "ts", "csv", "jpeg", "jpg", "gif", "png",  
    "tar", "xlsx", "xml", "zip"  
]  
  
with st.sidebar:  
    st.header("ファイルアップロード")  
    uploaded_file = st.file_uploader(  
        "サポートされているファイルを選択してください",  
        type=supported_types,  
        key="file_uploader"  
    )  
    if uploaded_file:  
        if (  
            "uploaded_file_info" not in st.session_state or  
            st.session_state.uploaded_file_info.get("name") != uploaded_file.name  
        ):  
            try:  
                # ファイル名を明示的に渡すことで、OpenAI側に正しい名前で登録される  
                file = client.files.create(  
                    file=(uploaded_file.name, uploaded_file),  # ここがポイント  
                    purpose="assistants"  
                )  
                file_id = file.id  
            except Exception as e:  
                st.error(f"ファイルアップロードに失敗: {e}")  
                file_id = None  
            if file_id:  
                st.session_state.uploaded_file_info = {  
                    "name": uploaded_file.name,  
                    "file_id": file_id  
                }  
                st.session_state.selected_analysis_file_id = file_id  # アップロード直後に自動選択  
                st.success(f"ファイル '{uploaded_file.name}' をアップロードしました。")  
                st.rerun()  
        else:  
            st.info(f"ファイル '{uploaded_file.name}' は既にアップロード済みです。")  
    else:  
        st.session_state.uploaded_file_info = {}  
  
    st.divider()  
    st.subheader("アップロード済みファイル一覧")  
  
    # ファイル一覧取得  
    try:  
        files = client.files.list().data  
    except Exception as e:  
        st.error(f"ファイル一覧の取得に失敗しました: {e}")  
        files = []  
  
    # ユニークな表示名を作成（重複は (2), (3), ... で区別）  
    name_counter = defaultdict(int)  
    display_name_to_id = {}  
    id_to_display_name = {}  
    display_names = []  
    for f in files:  
        name_counter[f.filename] += 1  
        if name_counter[f.filename] == 1:  
            display_name = f.filename  
        else:  
            display_name = f"{f.filename}({name_counter[f.filename]})"  
        display_name_to_id[display_name] = f.id  
        id_to_display_name[f.id] = display_name  
        display_names.append(display_name)  
  
    if files:  
        # デフォルトで選択されるindexを決める  
        default_index = 0  # （ファイルを指定しない）  
        if st.session_state.selected_analysis_file_id:  
            try:  
                selected_file_id = st.session_state.selected_analysis_file_id  
                selected_display_name = id_to_display_name.get(selected_file_id, None)  
                if selected_display_name:  
                    default_index = 1 + display_names.index(selected_display_name)  
            except Exception:  
                default_index = 0  
  
        # 分析対象ファイルの選択  
        selected_label = st.selectbox(  
            "分析するファイルを選択",  
            options=["（ファイルを指定しない）"] + display_names,  
            index=default_index,  
            key="analysis_file_selectbox"  
        )  
        if selected_label == "（ファイルを指定しない）":  
            st.session_state.selected_analysis_file_id = None  
        else:  
            st.session_state.selected_analysis_file_id = display_name_to_id[selected_label]  
  
        st.markdown("---")  
  
        # 削除対象ファイルの選択  
        selected_delete_labels = st.multiselect(  
            "削除したいファイルを選択",  
            options=display_names,  
            key="delete_files_multiselect"  
        )  
        if st.button("選択したファイルを削除"):  
            for display_name in selected_delete_labels:  
                file_id = display_name_to_id[display_name]  
                try:  
                    client.files.delete(file_id)  
                    st.success(f"{display_name} を削除しました")  
                    # 分析選択中のファイルが削除された場合は選択解除  
                    if st.session_state.selected_analysis_file_id == file_id:  
                        st.session_state.selected_analysis_file_id = None  
                except Exception as e:  
                    st.error(f"{display_name} の削除に失敗: {e}")  
            st.rerun()  
    else:  
        st.info("アップロード済みファイルはありません。")  
        st.session_state.selected_analysis_file_id = None  
  
# メインエリア：チャット履歴を交互に吹き出し形式で表示  
for msg in st.session_state.messages:  
    with st.chat_message(msg["role"]):  
        st.markdown(msg["content"])  
        if "images" in msg and msg["images"]:  
            for img in msg["images"]:  
                st.image(img)  
  
# チャット入力欄（ページ下部に固定、Enter送信）  
prompt = st.chat_input("質問や分析したい内容を入力してください")  
  
if prompt:  
    # 1. スレッド作成（初回のみ）  
    if not st.session_state.thread_id:  
        thread = client.beta.threads.create()  
        st.session_state.thread_id = thread.id  
    thread_id = st.session_state.thread_id  
  
    # 2. ユーザー発言を履歴に追加  
    st.session_state.messages.append({"role": "user", "content": prompt, "images": []})  
    with st.chat_message("user"):  
        st.markdown(prompt)  
  
    # 3. ファイル添付（サイドバーで選択したファイルがあれば）  
    attachments = []  
    selected_file_id = st.session_state.get("selected_analysis_file_id")  
    if selected_file_id:  
        attachments = [{  
            "file_id": selected_file_id,  
            "tools": [{"type": "code_interpreter"}]  
        }]  
  
    # 4. メッセージ送信  
    message = client.beta.threads.messages.create(  
        thread_id=thread_id,  
        role="user",  
        content=prompt,  
        attachments=attachments if attachments else None  
    )  
  
    # 5. Run作成  
    run = client.beta.threads.runs.create(  
        thread_id=thread_id,  
        assistant_id=ASSISTANT_ID  
    )  
  
    # 6. Run完了までポーリング  
    with st.spinner("AIが考え中..."):  
        while True:  
            run_status = client.beta.threads.runs.retrieve(thread_id=thread_id, run_id=run.id)  
            if run_status.status in ["completed", "failed", "cancelled", "requires_action"]:  
                break  
            time.sleep(2)  
  
    # 7. AI応答の取得  
    if run_status.status != "completed":  
        assistant_response = f"分析に失敗しました: {run_status.status}"  
        images = []  
    else:  
        messages = client.beta.threads.messages.list(thread_id=thread_id)  
        assistant_messages = [m for m in messages.data if m.role == "assistant"]  
        if assistant_messages:  
            msg = assistant_messages[0]  
            assistant_response = ""  
            images = []  
            for content in msg.content:  
                if content.type == "text":  
                    assistant_response += content.text.value  
                elif content.type == "image_file":  
                    image_file_id = content.image_file.file_id  
                    image_content = client.files.content(image_file_id)  
                    image_bytes = image_content.read()  
                    images.append(image_bytes)  
        else:  
            assistant_response = "アシスタントからの応答がありません。"  
            images = []  
  
    # 8. チャット履歴にAI応答追加（画像も保存）  
    st.session_state.messages.append({  
        "role": "assistant",  
        "content": assistant_response,  
        "images": images  
    })  
    with st.chat_message("assistant"):  
        st.markdown(assistant_response)  
        for img in images:  
            st.image(img)  