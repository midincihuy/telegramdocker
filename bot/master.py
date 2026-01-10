import os
import re
import time
from datetime import datetime, timedelta

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

import requests
from bs4 import BeautifulSoup

# ==== Load Environment ====
CREDENTIALS_PATH = os.getenv("CREDENTIALS_PATH", "/credentials/service_account.json")
SPREADSHEET_ID = os.getenv("SHEET_ID")
HOUR_BEFORE=os.getenv("HOUR_BEFORE")

# ==== Google API Setup ====
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
creds = Credentials.from_service_account_file(CREDENTIALS_PATH, scopes=SCOPES)
sheets_service = build('sheets', 'v4', credentials=creds)
service_email = creds.service_account_email
web_root = "https://admin.hsi.id"

def get_cell(sheet_service, spreadsheet_id, cell_range):
    result = sheet_service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id,
        range=cell_range
    ).execute()
    return result.get("values", [[""]])[0][0]

def get_rows(sheet_service, spreadsheet_id, range_name):
    result = sheet_service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id,
        range=range_name
    ).execute()
    return result.get("values", [])

def login():
    url = web_root+"/post/?view=login"

    headers = {
            "User-Agent": "Mozilla/5.0 (Python)",
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": web_root,
            "X-Requested-With": "XMLHttpRequest"
    }
    payloads = {
        "userid" : userid,
        "password" : password,
    }

    response = requests.post(url, headers=headers, data=payloads)
    response.raise_for_status()

    sessionid = response.cookies.get('sessionid')
    return sessionid

def set_evaluasi_aktif(service, spreadsheet_id, hour_before):
    now = datetime.now() - timedelta(hours=int(hour_before))

    result = get_rows(service, spreadsheet_id, "Evaluasi!A1:E")
    evaluasi = [row for row in result if row and row[0] != ""]

    for i in range(1, len(evaluasi)):
        e = evaluasi[i][1] if len(evaluasi[i]) > 1 else None
        start_str = evaluasi[i][2] if len(evaluasi[i]) > 2 else None
        end_str = evaluasi[i][3] if len(evaluasi[i]) > 3 else None

        try:
            start = datetime.fromisoformat(start_str)
            end = datetime.fromisoformat(end_str)
        except Exception:
            continue

        if start <= now < end:
            return e

    return None

def cek_evaluasi(service, spreadsheet_id):
    evaluasi = get_rows(service, spreadsheet_id, "Evaluasi!A2:B")
    arr_evaluasi = {}
    for x in evaluasi:
        code = x[0]
        name = x[1]
        arr_evaluasi[name] = code
    return arr_evaluasi

def get_arr_santri(service, spreadsheet_id, start, finish):
    santri = get_rows(service, spreadsheet_id, "AllUserId!A"+start+":C"+finish)
    arr_santri = {}
    for x in santri:
        userid = x[1]
        nip = x[2]
        arr_santri[nip] = userid
    return arr_santri

def get_total(service, spreadsheet_id):
    totals = get_rows(service, spreadsheet_id, "Total!A2:E")
    arr_totals = {}
    for x in totals:
        group = x[0]
        total = x[4]
        arr_totals[group] = total
    return arr_totals

def get_kelas(service, spreadsheet_id):
    data = get_rows(service, spreadsheet_id, "Kelas!A2:B")
    arr_data = {}
    for x in data:
        id = x[0]
        kls = x[1]
        arr_data[id] = kls
    return arr_data

def check_id(service, spreadsheet_id, ID, sheet_name, column="A"):
    range_name = f"{sheet_name}!{column}2:{column}"
    rows = get_rows(service, spreadsheet_id, range_name)

    if not rows:
        return False
    id_lists = [row[0] for row in rows if row]

    return ID in id_lists

def update_data(service, spreadsheet_id, range_name, values):
    body = {
        "values" : values
    }

    result = service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=range_name,
        valueInputOption="RAW",
        body=body
    ).execute()
    return result

def get_range_by_id(service, spreadsheet_id, sheet_name, record_id, last_col):
    if not record_id:
        return None
    range_name = F"{sheet_name}!A2:A"
    id_list = get_rows(service, spreadsheet_id, range_name)

    for i, row in enumerate(id_list):
        if len(row) > 0 and row[0] == record_id:
            row_number = i+2
            return f"{sheet_name}!A{row_number}:{last_col}{row_number}"
        
    return None


userid = get_cell(sheets_service, SPREADSHEET_ID, "Setting!H1")
password = get_cell(sheets_service, SPREADSHEET_ID, "Setting!I1")
group_module_id = get_cell(sheets_service, SPREADSHEET_ID, "Setting!J1")
program_id = get_cell(sheets_service, SPREADSHEET_ID, "Setting!K1")
kelas = get_rows(sheets_service, SPREADSHEET_ID, "Kelas!A2:C")
token = get_cell(sheets_service, SPREADSHEET_ID, "Setting!L1")
chat_id = get_cell(sheets_service, SPREADSHEET_ID, "Setting!F1")

def sendNotifTele(msg):
    tele_url = "https://api.telegram.org/bot"+token+"/sendMessage"
    payloads = {
        "chat_id" : chat_id,
        "text" : msg,
        "parse_mode" : "markdown"
    }
    response = requests.post(tele_url, data=payloads)

def get_time_evaluasi(start=2, finish="", hour_before=HOUR_BEFORE, chunk_size=300):
    counter=int(start)
    service, spreadsheet_id = sheets_service, SPREADSHEET_ID
    evaluasi = set_evaluasi_aktif(service, spreadsheet_id, hour_before)
    if(evaluasi):
        sessionId = login()
        if(sessionId):
            list_evaluasi = cek_evaluasi(service, spreadsheet_id)
            lesson_id = list_evaluasi[evaluasi]
            arr_santri = get_arr_santri(service, spreadsheet_id, start, finish)
            big_data = []
            for nip in arr_santri:
                id_santri = arr_santri[nip]
                url = web_root

                headers = {
                        "User-Agent": "Mozilla/5.0 (Python)",
                        "Content-Type": "application/x-www-form-urlencoded",
                        "Referer": web_root,
                        "X-Requested-With": "XMLHttpRequest",
                        "Cookie" : "sessionid=" + sessionId
                }

                gettimeUrl = url + "?user_id="+id_santri+"&view=ooc-form&subgroup_id=&program_id="+program_id+"&group_module_id="+group_module_id+"&lesson_id="+lesson_id
                response = requests.get(gettimeUrl, headers=headers)
                soup = BeautifulSoup(response.text, "html.parser")
                element = soup.find(class_="text-right")
                if(element):
                    nilai = 0

                    for row in soup.find_all("div",class_="row"):
                        text = row.get_text(" ", strip=True)
                        match_nilai = re.search(r"\((\d+)\s*/\s*\d+\)", text)
                        if match_nilai:
                            nilai = match_nilai.group(1)
                    match = re.search(r"Mulai:\s*([\d\-:\s]+)",element.text.strip())
                    if match:
                        mulai = match.group(1).strip()
                    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    mulai_dt = datetime.strptime(mulai, "%Y-%m-%d %H:%M:%S")
                    dt = mulai_dt.strftime("%m/%d/%Y")
                    hour = mulai_dt.hour
                    obj_santri = [str(id_santri + "|" + nip + "@" + evaluasi), mulai, now, id_santri + "|" + nip, evaluasi, dt, hour, int(nilai)]
                    big_data.append(obj_santri)
                    print(obj_santri)
                    time.sleep(1)
                counter+=1
            print("start chunking")
            for i in range(0, len(big_data), chunk_size):
                chunk = big_data[i:i+chunk_size]

                body = {
                    "values" : chunk,
                    "majorDimension" : "ROWS"
                }
                print(body)
                service.spreadsheets().values().append(
                    spreadsheetId=spreadsheet_id,
                    range=f"RawTime!A:C",
                    valueInputOption="RAW",
                    insertDataOption="INSERT_ROWS",
                    body=body
                ).execute()


            # send notif to tele
            sendNotifTele("success save rawtime Start : "+str(start)+" Finish : "+str(finish)+" hour : "+str(hour_before))

def get_klasemen(hour_before=HOUR_BEFORE):
    service, spreadsheet_id = sheets_service, SPREADSHEET_ID
    evaluasi = set_evaluasi_aktif(service, spreadsheet_id, hour_before)
    if(evaluasi):
        sessionId = login()
        if(sessionId):
            total = get_total(service, spreadsheet_id)
            list_evaluasi = cek_evaluasi(service, spreadsheet_id)
            lesson_id = list_evaluasi[evaluasi]
            url = web_root

            headers = {
                    "User-Agent": "Mozilla/5.0 (Python)",
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Referer": web_root,
                    "X-Requested-With": "XMLHttpRequest",
                    "Cookie" : "sessionid=" + sessionId
            }

            getklasemenUrl = url + "?view=ooc-form&subgroup_id=Rekap&program_id="+program_id+"&group_module_id="+group_module_id+"&lesson_id="+lesson_id
            response = requests.get(getklasemenUrl, headers=headers)
            soup = BeautifulSoup(response.text, "html.parser")
            element = soup.find(class_="card-body")
            if(element):
                data = []
                rows = element.find_all("div", class_="row")
                for row in rows:
                    cols = row.find_all("div", class_="col-md-2")
                    if len(cols) < 3:
                        continue
                    group_text = cols[0].get_text(strip=True)
                    group_name = group_text.split("•")[0].strip()

                    # kosong_text = cols[2].get_text(strip=True)
                    kosong_number = None
                    kosong_div = cols[2].find("div", string=lambda x: x and "Kosong" in x)
                    if kosong_div:
                        text = kosong_div.get_text(strip=True)
                        kosong_number = int(text.replace("Kosong", "").strip())
                    data.append({
                        group_name : kosong_number
                    })
                message = ".   ━━✮✪✮━━\n"
                message +="┏━✿✿❀❀✬❀❀✿✿━┓\n"
                message +="*Klasemen "+evaluasi+"*\n"
                message +="┗━✷✷✺✺✩✺✺✷✷━┛\n"
                message +="➖➖➖➖➖➖➖➖➖➖➖\n"
                message +="\n"
                message +="0️⃣6️⃣┃"+str(data[0]['ARN202-06'])+" / "+str(total['ARN202-06'])+"\n"
                message +="0️⃣7️⃣┃"+str(data[1]['ARN202-07'])+" / "+str(total['ARN202-07'])+"\n"
                message +="0️⃣8️⃣┃"+str(data[2]['ARN202-08'])+" / "+str(total['ARN202-08'])+"\n"
                message +="0️⃣9️⃣┃"+str(data[3]['ARN202-09'])+" / "+str(total['ARN202-09'])+"\n"
                message +="1️⃣0️⃣┃"+str(data[4]['ARN202-10'])+" / "+str(total['ARN202-10'])+"\n"
                message +="\n"
                message +=".           ━━━━✩✭✩✭✩━━━━"
                
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                # mulai_dt = datetime.strptime(mulai, "%Y-%m-%d %H:%M:%S")
                # dt = mulai_dt.strftime("%m/%d/%Y")
                # hour = mulai_dt.hour
                # obj_santri = [str(id_santri + "|" + nip + "@" + evaluasi), mulai, now, id_santri + "|" + nip, evaluasi, dt, hour, int(nilai)]

                json_var = [
                    {
                        'Group' : "ARN202-06|"+evaluasi,
                        'Kosong' : data[0]['ARN202-06'],
                        'Waktu' : now
                    },
                    {
                        'Group' : "ARN202-07|"+evaluasi,
                        'Kosong' : data[1]['ARN202-07'],
                        'Waktu' : now
                    },
                    {
                        'Group' : "ARN202-08|"+evaluasi,
                        'Kosong' : data[2]['ARN202-08'],
                        'Waktu' : now
                    },
                    {
                        'Group' : "ARN202-09|"+evaluasi,
                        'Kosong' : data[3]['ARN202-09'],
                        'Waktu' : now
                    },
                    {
                        'Group' : "ARN202-10|"+evaluasi,
                        'Kosong' : data[4]['ARN202-10'],
                        'Waktu' : now
                    }
                ]
                for data in json_var:
                    values = [[data['Group'], data['Kosong'], data['Waktu']]]
                    if check_id(service, spreadsheet_id, data['Group'], 'Klasemen'):
                        range_id = get_range_by_id(service, spreadsheet_id, "Klasemen", data['Group'], "C")
                        # print(range_id)
                        update_data(service, spreadsheet_id,range_id,values)
                    else:
                        service.spreadsheets().values().append(
                            spreadsheetId=spreadsheet_id,
                            range=f"Klasemen!A:C",
                            valueInputOption="RAW",
                            insertDataOption="INSERT_ROWS",
                            body={"values": values}
                        ).execute()
            # send notif to tele
            sendNotifTele(message)
        else:
            sendNotifTele("Failed to Login")
    else:
        sendNotifTele("No Evaluasi")

def get_skor():
    service, spreadsheet_id = sheets_service, SPREADSHEET_ID
    sessionId = login()
    if(sessionId):
        group = get_kelas(service,spreadsheet_id)
        # print(group) # [['tNb0q5V', 'ARN202-07'], ['wU3cSXQ', 'ARN202-08'], ['9IFt4qD', 'ARN202-09'], ['vfGaRmZ', 'ARN202-10'], ['UgUWMQa', 'ARN202-11'], ['AaZB3EU', 'ARN202-12'], ['laqMXar', 'ARN202-13']]
        for group_id, kelas in group.items():
            # print(group[key])
            url = web_root

            headers = {
                    "User-Agent": "Mozilla/5.0 (Python)",
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Referer": web_root,
                    "X-Requested-With": "XMLHttpRequest",
                    "Cookie" : "sessionid=" + sessionId
            }

            getSkorUrl = url + "?view=ooc-rating-score&subgroup_id="+group_id+"&program_id="+program_id+"&group_module_id="+group_module_id
            response = requests.get(getSkorUrl, headers=headers)
            soup = BeautifulSoup(response.text, "html.parser")
            element = soup.find(class_="card-body")
            skor = []
            if(element):
                cards = soup.select(".card-body .d-flex")
                for card in cards:
                # print(element)
                # print("===========================")
                    text = card.get_text(" ", strip=True)

                    id_tag = card.find("span", class_="badge-soft-success")
                    id_santri = id_tag.get_text(strip=True)

                    after_id = text.split(id_santri)[1].strip()
                    student_name = after_id.split("|")[0].strip()

                    score_tag = card.find("span", class_="badge-soft-primary").find("a")
                    score_list = score_tag.get_text(strip=True)

                                       
                    obj_santri = [str(id_santri),student_name, score_list]
                    skor.append(obj_santri)
                # print(skor)
                # do clear Sheet Skor per Group
                service.spreadsheets().values().clear(
                    spreadsheetId=spreadsheet_id,
                    range=f"Skor {kelas}!A2:C500",
                    body={}
                ).execute()
                time.sleep(2)
                service.spreadsheets().values().append(
                    spreadsheetId=spreadsheet_id,
                    range=f"Skor {kelas}!A2:C",
                    valueInputOption="RAW",
                    insertDataOption="OVERWRITE",
                    body={"values": skor}
                ).execute()
                sendNotifTele(f"Finish update skor {kelas}")
    else:
        sendNotifTele("Failed to Login")