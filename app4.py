import os  
import streamlit as st  
import openai  
import time  
from collections import defaultdict  
  
# Azure OpenAIの設定（環境変数から取得）  
AZURE_OPENAI_KEY = os.getenv("AZURE_OPENAI_KEY")  
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")  
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")  
ASSISTANT_ID = os.getenv("AZURE_OPENAI_ASSISTANT_ID")  
  
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
if "selected_analysis_file_ids" not in st.session_state:  
    st.session_state.selected_analysis_file_ids = []  
  
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
                file = client.files.create(  
                    file=(uploaded_file.name, uploaded_file),  
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
                if file_id not in st.session_state.selected_analysis_file_ids:  
                    st.session_state.selected_analysis_file_ids.append(file_id)  
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
  
    user_files = files  
  
    # ユニークな表示名を作成（重複は (2), (3), ... で区別）  
    name_counter = defaultdict(int)  
    display_name_to_id = {}  
    id_to_display_name = {}  
    display_names = []  
    for f in user_files:  
        name_counter[f.filename] += 1  
        if name_counter[f.filename] == 1:  
            display_name = f.filename  
        else:  
            display_name = f"{f.filename}({name_counter[f.filename]})"  
        display_name_to_id[display_name] = f.id  
        id_to_display_name[f.id] = display_name  
        display_names.append(display_name)  
  
    if user_files:  
        # 現在の選択状態をdisplay_nameリストに変換  
        current_selected_display_names = [  
            id_to_display_name[fid] for fid in st.session_state.selected_analysis_file_ids if fid in id_to_display_name  
        ]  
  
        # 複数ファイル選択（選択状態をセッションと同期）  
        selected_display_names = st.multiselect(  
            "分析するファイルを選択（複数可）",  
            options=display_names,  
            default=current_selected_display_names,  
            key="analysis_file_multiselect"  
        )  
        st.session_state.selected_analysis_file_ids = [  
            display_name_to_id[name] for name in selected_display_names  
        ]  
  
        # すべて選択・選択解除ボタン  
        col1, col2 = st.columns(2)  
        with col1:  
            if st.button("すべて選択"):  
                st.session_state.selected_analysis_file_ids = [display_name_to_id[name] for name in display_names]  
                st.rerun()  
        with col2:  
            if st.button("選択解除"):  
                st.session_state.selected_analysis_file_ids = []  
                st.rerun()  
  
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
                    if file_id in st.session_state.selected_analysis_file_ids:  
                        st.session_state.selected_analysis_file_ids.remove(file_id)  
                except Exception as e:  
                    st.error(f"{display_name} の削除に失敗: {e}")  
            st.rerun()  
    else:  
        st.info("アップロード済みファイルはありません。")  
        st.session_state.selected_analysis_file_ids = []  
  
# メインエリア：チャット履歴+途中プロセス  
for msg in st.session_state.messages:  
    with st.chat_message(msg["role"]):  
        st.markdown(msg["content"])  
        if "images" in msg and msg["images"]:  
            for img in msg["images"]:  
                st.image(img)  
        # 途中プロセス（run_steps）があれば表示  
        if "run_steps" in msg and msg["run_steps"]:  
            with st.expander("途中プロセスを見る", expanded=False):  
                for step in msg["run_steps"]:  
                    st.markdown(step)  
  
# チャット入力欄  
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
  
    # 3. ファイル添付  
    selected_file_ids = st.session_state.get("selected_analysis_file_ids", [])  
    attachments = []  
    for file_id in selected_file_ids:  
        attachments.append({  
            "file_id": file_id,  
            "tools": [{"type": "code_interpreter"}]  
        })  
  
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
  
    # 7. 途中プロセス（Run Steps）を取得  
    run_steps_details = []  
    try:  
        run_steps = client.beta.threads.runs.steps.list(  
            thread_id=thread_id,  
            run_id=run.id  
        )  
        # ステップごとに詳細取得  
        for step in run_steps.data:  
            detail = client.beta.threads.runs.steps.retrieve(  
                thread_id=thread_id,  
                run_id=run.id,  
                step_id=step.id  
            )  
            # Code Interpreter実行内容を抽出  
            step_markdown = ""  
            if hasattr(detail, "step_details") and hasattr(detail.step_details, "tool_calls"):  
                for tool_call in detail.step_details.tool_calls:  
                    if hasattr(tool_call, "code_interpreter"):  
                        ci = tool_call.code_interpreter  
                        if hasattr(ci, "input"):  
                            step_markdown += f"**実行コード:**\n```python\n{ci.input}\n```\n"  
                        if hasattr(ci, "outputs"):  
                            for output in ci.outputs:  
                                if hasattr(output, "logs") and output.logs:  
                                    step_markdown += f"**ログ:**\n```\n{output.logs}\n```\n"  
                                if hasattr(output, "text") and output.text:  
                                    step_markdown += f"**出力:**\n```\n{output.text}\n```\n"  
            if step_markdown:  
                run_steps_details.append(step_markdown)  
    except Exception as e:  
        run_steps_details = [f"途中プロセスの取得に失敗: {e}"]  
  
    # 8. AI応答の取得  
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
                    try:  
                        client.files.delete(image_file_id)  
                    except Exception as e:  
                        st.warning(f"一時画像ファイルの削除に失敗: {e}")  
        else:  
            assistant_response = "アシスタントからの応答がありません。"  
            images = []  
  
    # 9. チャット履歴にAI応答追加（途中プロセスも保存）  
    st.session_state.messages.append({  
        "role": "assistant",  
        "content": assistant_response,  
        "images": images,  
        "run_steps": run_steps_details  
    })  
    with st.chat_message("assistant"):  
        st.markdown(assistant_response)  
        for img in images:  
            st.image(img)  
        if run_steps_details:  
            with st.expander("途中プロセスを見る", expanded=False):  
                for step in run_steps_details:  
                    st.markdown(step)  