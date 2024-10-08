import google.generativeai as genai
from flask import Flask,request,jsonify
import requests
import os
import fitz
import json
import re
import urllib.parse
import ast
from datetime import datetime, timedelta

wa_token=os.environ.get("WA_TOKEN")
genai.configure(api_key=os.environ.get("GEN_API"))
phone_id=os.environ.get("PHONE_ID")
#phone=os.environ.get("PHONE_NUMBER")
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
    pattern = r'\[([^,\]]+),\s*([^,\]]+),\s*([^,\]]+),\s*([^\]]*)\]'
    match = re.search(pattern, text)
    if not match:
        return ['TBC'] * 4, 'TBC', 'TBC', 'TBC', 'TBC'

    gcal_list = list(match.groups())
    gcal_list = [item.strip().strip("'") for item in gcal_list]  # 移除開頭和結尾的空白和單引號
    title, date, location, desc = gcal_list

    # 處理日期格式
    date = process_date(date)

    return gcal_list, title, date, location, desc

def extract_sender_phone(webhook_data):
    try:
        # 從 webhook 數據中提取訊息部分
        message = webhook_data["entry"][0]["changes"][0]["value"]["messages"][0]
        
        # 提取發送者的電話號碼
        sender_phone = message["from"]
        
        return sender_phone
    except KeyError:
        # 如果無法找到預期的鍵，返回 None
        return None
    except IndexError:
        # 如果列表索引超出範圍，返回 None
        return None

def process_date(date_str):
    # 如果日期字符串為空或 'TBC'，返回當前時間加一小時
    if not date_str or date_str == 'TBC':
        now = datetime.now()
        end = now + timedelta(hours=1)
        print(f"{now.strftime('%Y%m%dT%H%M%S')}/{end.strftime('%Y%m%dT%H%M%S')}")
        return f"{now.strftime('%Y%m%dT%H%M%S')}/{end.strftime('%Y%m%dT%H%M%S')}"

    # 如果日期字符串已經包含結束時間，直接返回
    if '/' in date_str:
        start, end = date_str.split('/')
        print(f"{start}/{end}")
        return date_str

    # 否則，假設結束時間為開始時間加一小時
    try:
        start = datetime.strptime(date_str, '%Y%m%dT%H%M%S')
        end = start + timedelta(hours=1)
        print(f"{start.strftime('%Y%m%dT%H%M%S')}/{end.strftime('%Y%m%dT%H%M%S')}")
        return f"{start.strftime('%Y%m%dT%H%M%S')}/{end.strftime('%Y%m%dT%H%M%S')}"
    except ValueError:
        # 如果日期格式不正確，返回當前時間加一小時
        now = datetime.now()
        end = now + timedelta(hours=1)
        print(f"{now.strftime('%Y%m%dT%H%M%S')}/{end.strftime('%Y%m%dT%H%M%S')}")
        return f"{now.strftime('%Y%m%dT%H%M%S')}/{end.strftime('%Y%m%dT%H%M%S')}"

def create_gcal_url(title='看到這個..請重生', date='20230524T180000/20230524T220000', location='那邊', description=''):
  #https://calendar.google.com/calendar/u/0/r/eventedit?text=%E9%87%8D%E8%A6%81%E6%9C%83%E8%AD%B0&dates=20240101T090000/20240101T100000&location=%E5%8F%B0%E5%8C%97101&details=%E8%A8%8E%E8%AB%96%E5%B9%B4%E5%BA%A6%E9%A0%90%E7%AE%97&add=colleague@example.com
    base_url = "https://calendar.google.com/calendar/u/0/r/eventedit?"
    event_url = f"{base_url}&text={urllib.parse.quote(title)}&dates={date}&location={urllib.parse.quote(location)}&details={urllib.parse.quote(description)}"
    return event_url + "&openExternalBrowser=1"
	


def process_user_input(user_input):
    # 設置模型
    model = genai.GenerativeModel('gemini-pro')

    # 定義自定義提示
    custom_prompt = """You are a bot that can parse text and convert it into a Python array format.
Given the following prompt: Organize the following content into "title", "time", "location", and "description".
Example: ['Dinner with colleagues', 20240627T230000/20240627T233000, 'Megastart', 'description content']
Ensure the time format is YYYYMMDDTHHmmss, and if the end time is not explicitly provided, default it to 1 hour after the start time. The current year is 2024. Please only return the array, without any additional explanations or formatting.the description content is user`s input。"""

    # 啟動對話
    convo = model.start_chat(
        history=[
            {"role": "user", "parts": [custom_prompt]},
            {"role": "model", "parts": ["acknowledged,I will translate to array in python"]}
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

	
def process_response(response):
    return response.text.strip()
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


def sendtest(answer,phone5):
    url=f"https://graph.facebook.com/v18.0/{phone_id}/messages"
    headers={
        'Authorization': f'Bearer {wa_token}',
        'Content-Type': 'application/json'
    }
    data={
          "messaging_product": "whatsapp", 
          "to": f"{phone5}", 
          "type": "text",
          "text":{"body": f"{phone5}"},
          }
    
    response=requests.post(url, headers=headers,json=data)
    return response
def send(answer, sender_phone):
    url=f"https://graph.facebook.com/v18.0/{phone_id}/messages"
    headers={
        'Authorization': f'Bearer {wa_token}',
        'Content-Type': 'application/json'
    }
    data={
          "messaging_product": "whatsapp", 
          "to": f"{sender_phone}", 
          "type": "text",
          "text":{"body": f"{answer}"},
          }
    
    response=requests.post(url, headers=headers,json=data)
    return response

def remove(*file_paths):
    for file in file_paths:
        if os.path.exists(file):
            os.remove(file)
        else:pass

#user_input='我9月6日0900要去台北吃飯，會有很多的貴賓'
#response = process_user_input(user_input)
#send(response)

#@app.route("/",methods=["GET","POST"])
#def index():
#    return "Bot"
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
            webhook_data = request.get_json()
            data = webhook_data["entry"][0]["changes"][0]["value"]["messages"][0]
            sender_phone = extract_sender_phone(webhook_data)
            
            if data["type"] == "text":
                prompt = data["text"]["body"]
                response = process_user_input(prompt)
                sendtest("abcd", sender_phone)
                send(response, sender_phone)  # 修復：移除多餘的參數
            else:
                # 處理媒體消息
                media_url_endpoint = f'https://graph.facebook.com/v18.0/{data[data["type"]]["id"]}/'
                headers = {'Authorization': f'Bearer {wa_token}'}
                media_response = requests.get(media_url_endpoint, headers=headers)
                media_url = media_response.json()["url"]
                media_download_response = requests.get(media_url, headers=headers)
                
                if data["type"] in ["audio", "image"]:
                    filename = f"/tmp/temp_{data['type']}.{'mp3' if data['type'] == 'audio' else 'jpg'}"
                    with open(filename, "wb") as temp_media:
                        temp_media.write(media_download_response.content)
                    file = genai.upload_file(path=filename, display_name="tempfile")
                    response = model.generate_content(["What is this", file])
                    answer = response._result.candidates[0].content.parts[0].text
                    send(f"This is a {data['type']} message from user. Here's what I understand: {answer}")
                    remove(filename)
                elif data["type"] == "document":
                    doc = fitz.open(stream=media_download_response.content, filetype="pdf")
                    for page in doc:
                        destination = "/tmp/temp_image.jpg"
                        pix = page.get_pixmap()
                        pix.save(destination)
                        file = genai.upload_file(path=destination, display_name="tempfile")
                        response = model.generate_content(["What is this", file])
                        answer = response._result.candidates[0].content.parts[0].text
                        send(f"This is a document. Here's what I understand from page {page.number + 1}: {answer}")
                        remove(destination)
                else:
                    send("This format is not supported by the bot ☹")
                
                # 清理上傳的文件
                for file in genai.list_files():
                    file.delete()
        except Exception as e:
            print(f"Error processing webhook: {str(e)}")
        return jsonify({"status": "ok"}), 200
if __name__ == "__main__":
    app.run(debug=True, port=8000)
