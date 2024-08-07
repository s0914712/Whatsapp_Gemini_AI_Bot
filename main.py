import os
from openai import OpenAI
from flask import Flask, request, jsonify
import requests
import re
import urllib.parse
import ast

WHATSAPP_TOKEN=os.environ.get("WA_TOKEN")
WHATSAPP_PHONE_NUMBER_ID=os.environ.get("PHONE_ID")
phone=os.environ.get("PHONE_NUMBER")
OPENAI_API_KEY=os.environ.get("OPENAI_API_KEY")

app = Flask(__name__)
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

# WhatsApp API 設置
WHATSAPP_URL = f'https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_NUMBER_ID}/messages'


def send_whatsapp_message(to, message):
    headers = {
        'Authorization': f'Bearer {WHATSAPP_TOKEN}',
        'Content-Type': 'application/json'
    }
    data = {
        'messaging_product': 'whatsapp',
        'to': to,
        'type': 'text',
        'text': {'body': message}
    }
    response = requests.post(WHATSAPP_URL, headers=headers, json=data)
    return response.json()

def create_gcal_url(title='TBC', date='20240101T000000/20240101T010000', location='TBC', description=''):
    base_url = "https://www.google.com/calendar/render?action=TEMPLATE"
    event_url = f"{base_url}&text={urllib.parse.quote(title)}&dates={date}&location={urllib.parse.quote(location)}&details={urllib.parse.quote(description)}"
    return event_url + "&openExternalBrowser=1"

class GPT_Cal:
    def __init__(self):
        self.model = "gpt-3.5-turbo"
        self.text = ""

    def get_response(self):
        response = client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": f"""
            將以下內容整理成標題、時間、地點、描述。
            範例: ['與同事聚餐', '20240627T230000/20240627T233000', '美麗華', '具體描述']
            請確保時間格式為 YYYYMMDDTHHmmss，如果沒有明確的結束時間，預設為開始時間後1小時。
            現在是 2024 年。請通過陣列回傳結果。
            {self.text}
            """}]
        )
        processed_text = response.choices[0].message.content
        gcal_list = ast.literal_eval(processed_text)
        title, date, location, desc = gcal_list
        gcal_url = create_gcal_url(title, date, location, desc)
        return gcal_url

    def add_msg(self, text):
        self.text = text

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()
    try:
        for entry in data['entry']:
            for change in entry['changes']:
                if change['field'] == 'messages':
                    messages = change['value']['messages']
                    for message in messages:
                        if message['type'] == 'text':
                            phone_number = message['from']
                            message_body = message['text']['body']
                            
                            # 使用 GPT_Cal 處理消息
                            gpt_cal = GPT_Cal()
                            gpt_cal.add_msg(message_body)
                            gcal_url = gpt_cal.get_response()
                            
                            # 發送 Google Calendar URL 回覆
                            response_message = f"這是您的 Google Calendar 邀請連結：\n{gcal_url}"
                            send_whatsapp_message(phone_number, response_message)
    except Exception as e:
        print(f"Error processing webhook: {str(e)}")
    
    return jsonify({"status": "ok"}), 200

@app.route('/', methods=['GET'])
def verify():
    if request.args.get("hub.mode") == "subscribe" and request.args.get("hub.challenge"):
        if not request.args.get("hub.verify_token") == os.environ.get("VERIFY_TOKEN"):
            return "Verification token mismatch", 403
        return request.args["hub.challenge"], 200
    return "Hello world", 200

if __name__ == '__main__':
    app.run(debug=True, port=5000)
