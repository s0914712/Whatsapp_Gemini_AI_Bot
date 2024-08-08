import google.generativeai as genai
from flask import Flask,request,jsonify
import requests
import os
import fitz
import json
import re
import urllib.parse
import ast
wa_token=os.environ.get("WA_TOKEN")
genai.configure(api_key=os.environ.get("GEN_API"))
phone_id=os.environ.get("PHONE_ID")
phone=os.environ.get("PHONE_NUMBER")
name="Your name or nickname" #The bot will consider this person as its owner or creator
bot_name="Give a name to your bot" #This will be the name of your bot, eg: "Hello I am Astro Bot"
model_name="gemini-1.5-flash-latest" #Switch to "gemini-1.0-pro" or any free model, if "gemini-1.5-flash" becomes paid in future.

app=Flask(__name__)

generation_config = {
  "temperature": 1,
  "top_p": 0.95,
  "top_k": 0,
  "max_output_tokens": 8192,
}

def extract_gcal_info(text):
    # 使用正則表達式直接從文本中提取所需信息
    pattern = r'\[([^,\]]+),\s*([^,\]]+),\s*([^,\]]+),\s*([^\]]*)\]'
    match = re.search(pattern, text)
    if not match:
        return ['TBC'] * 4, 'TBC', 'TBC', 'TBC', 'TBC'
    
    gcal_list = list(match.groups())
    title, date, location, desc = gcal_list
    
    # 清理並填充缺失的值
    gcal_list = [item.strip() or 'TBC' for item in gcal_list]
    title = gcal_list[0]
    date = gcal_list[1]
    location = gcal_list[2]
    desc = gcal_list[3]
    
    return gcal_list, title, date, location, desc

def is_url_valid(url):
    regex = re.compile(
        r'^(?:http|ftp)s?://'  # http:// or https://
        # domain...
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|'
        r'localhost|'  # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    return re.match(regex, url) is not None


def delete_strings(s):
    # Step 1: Delete all contents from '#' to the next '&' character
    s = re.sub(r'#[^&]*', '', s)

    # Step 2: If '&openExternalBrowser=1' is not at the end, add it
    if '&openExternalBrowser=1' != s:
        s += '&openExternalBrowser=1'
    return s


def create_gcal_url(
        title='看到這個..請重生',
        date='20230524T180000/20230524T220000',
        location='那邊',
        description=''):
    base_url = "https://www.google.com/calendar/render?action=TEMPLATE"
    event_url = f"{base_url}&text={urllib.parse.quote(title)}&dates={date}&location={urllib.parse.quote(location)}&details={urllib.parse.quote(description)}"
    return event_url + "&openExternalBrowser=1"

def process_response(response):
    # 提取回應中的文本內容
    text = response.text

    # 移除可能的 Markdown 代碼塊標記
    text = text.replace("```json", "").replace("```", "").strip()

    try:
        # 解析 JSON 字符串為 Python 列表
        result = json.loads(text)
        return result

    except json.JSONDecodeError:
        # 如果 JSON 解析失敗，直接返回原始文本
        return text

def process_user_input(user_input):
    # 設置模型
    model = genai.GenerativeModel('gemini-pro')

    # 定義自定義提示
    custom_prompt = """你是一個可以將文字解析轉換成python 陣列格式的bot，
    收到以下提示： 將以下內容整理成標題、時間、地點、描述。
    範例: ['與同事聚餐', '20240627T230000/20240627T233000', '美麗華', '其他內容放置處']
    請確保時間格式為 YYYYMMDDTHHmmss，如果沒有明確的結束時間，預設為開始時間後1小時。 現在是 2024 年。請只回傳陣列，不要加任何其他說明或格式。"""

    # 啟動對話
    convo = model.start_chat(
        history=[
            {"role": "user", "parts": [custom_prompt]},
            {"role": "model", "parts": ["理解，我將按要求處理輸入並只回傳陣列格式結果。"]}
        ]
    )

    response = convo.send_message(user_input)
    result = process_response(response)

    # 使用 extract_gcal_info 函數處理結果
    gcal_list, title, date, location, desc = extract_gcal_info(result)

    # 使用 create_gcal_url 函數生成 Google Calendar URL
    gcal_url = create_gcal_url(title, date, location, desc)

    # 創建一個包含事件詳情和 Google Calendar URL 的回覆消息
    reply_message = f"Event Details:\nTitle: {title}\nDate: {date}\nLocation: {location}\nDescription: {desc}\n\nAdd to Google Calendar: {gcal_url}"

    return reply_message

def send(answer):
    url=f"https://graph.facebook.com/v18.0/{phone_id}/messages"
    headers={'Authorization': f'Bearer {wa_token}','Content-Type': 'application/json'}
    data={"messaging_product": "whatsapp","to": f"{phone}","type": "text","text":{"body": f"{answer}"},}

    response=requests.post(url, headers=headers,json=data)
    return response

def remove(*file_paths):
    for file in file_paths:
        if os.path.exists(file):
            os.remove(file)
        else:pass

@app.route("/",methods=["GET","POST"])
def index():
    return "Bot"

@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    if request.method == "GET":
        mode = request.args.get("hub.mode")
        token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")
        if mode == "subscribe" and token == "BOT":
            return challenge, 200
        else:
            return "Failed", 403
    elif request.method == "POST":
        try:
            data = request.get_json()["entry"][0]["changes"][0]["value"]["messages"][0]
            if data["type"] == "text":
                user_input = data["text"]["body"]
                response = process_user_input(user_input)
                send(response)
            else:
                media_url_endpoint = f'https://graph.facebook.com/v18.0/{data[data["type"]]["id"]}/'
                headers = {'Authorization': f'Bearer {wa_token}'}
                media_response = requests.get(media_url_endpoint, headers=headers)
                media_url = media_response.json()["url"]
                media_download_response = requests.get(media_url, headers=headers)
                if data["type"] == "audio":
                    filename = "/tmp/temp_audio.mp3"
                elif data["type"] == "image":
                    filename = "/tmp/temp_image.jpg"
                elif data["type"] == "document":
                    doc=fitz.open(stream=media_download_response.content,filetype="pdf")
                    for _,page in enumerate(doc):
                        destination="/tmp/temp_image.jpg"
                        pix = page.get_pixmap()
                        pix.save(destination)
                        file = genai.upload_file(path=destination,display_name="tempfile")
                        response = model.generate_content(["What is this",file])
                        answer=response._result.candidates[0].content.parts[0].text
                        convo.send_message(f"This message is created by an llm model based on the image prompt of user, reply to the user based on this: {answer}")
                        send(convo.last.text)
                        remove(destination)
                else:send("This format is not Supported by the bot ☹")
                with open(filename, "wb") as temp_media:
                    temp_media.write(media_download_response.content)
                file = genai.upload_file(path=filename,display_name="tempfile")
                response = model.generate_content(["What is this",file])
                answer=response._result.candidates[0].content.parts[0].text
                remove("/tmp/temp_image.jpg","/tmp/temp_audio.mp3")
                convo.send_message(f"This is an voice/image message from user transcribed by an llm model, reply to the user based on the transcription: {answer}")
                send(convo.last.text)
                files=genai.list_files()
                for file in files:
                    file.delete()
        except :pass
        return jsonify({"status": "ok"}), 200
if __name__ == "__main__":
    app.run(debug=True, port=8000)

