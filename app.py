import os
import logging
from flask import Flask, render_template, request
from dotenv import load_dotenv, find_dotenv
import requests
from urllib.parse import quote_plus

# Load .env variables
dotenv_path = find_dotenv()
load_dotenv(dotenv_path, override=True)  # ensure latest keys :contentReference[oaicite:3]{index=3}

API_KEY  = os.getenv('RIOT_API_KEY')
PLATFORM = os.getenv('PLATFORM', 'euw1')   # for Summoner-V4
REGION   = os.getenv('REGION', 'europe')   # for Account-V1 & Match-V5

if not API_KEY:
    raise RuntimeError("Missing RIOT_API_KEY in .env")

app = Flask(__name__)
app.logger.setLevel(logging.DEBUG)

class ExpiredAPIKeyError(Exception):
    pass

def riot_request(url, params=None):
    """Header auth first, then fallback to ?api_key"""
    headers = {'X-Riot-Token': API_KEY}
    resp = requests.get(url, headers=headers, params=params)
    app.logger.debug(f"REQ → {resp.request.url}")
    if resp.status_code == 403:
        resp = requests.get(url, params={**(params or {}), 'api_key': API_KEY})
        app.logger.debug(f"REQ fallback → {resp.request.url}")
    if resp.status_code == 403:
        raise ExpiredAPIKeyError
    resp.raise_for_status()
    return resp.json()

@app.route('/', methods=['GET','POST'])
def home():
    data, error = None, None
    if request.method == 'POST':
        gn = request.form['gameName'].strip()
        tl = request.form['tagLine'].strip()
        if not gn or not tl:
            error = "Both Game Name and Tag Line are required."
        else:
            try:
                # 1) Account-V1 by Riot ID :contentReference[oaicite:4]{index=4}
                acct = riot_request(
                    f"https://{REGION}.api.riotgames.com"
                    f"/riot/account/v1/accounts/by-riot-id/"
                    f"{quote_plus(gn)}/{quote_plus(tl)}"
                )
                puuid = acct['puuid']

                # 2) Summoner-V4 by PUUID :contentReference[oaicite:5]{index=5}
                summ = riot_request(
                    f"https://{PLATFORM}.api.riotgames.com"
                    f"/lol/summoner/v4/summoners/by-puuid/{puuid}"
                )

                # 3) Match-V5 IDs by PUUID :contentReference[oaicite:6]{index=6}
                matches = riot_request(
                    f"https://{REGION}.api.riotgames.com"
                    f"/lol/match/v5/matches/by-puuid/{puuid}/ids",
                    params={'start': 0, 'count': 5}
                )

                data = {'account': acct, 'summoner': summ, 'matches': matches}
            except ExpiredAPIKeyError:
                error = ("Your Riot API key is invalid/expired. "
                         "Regenerate at developer.riotgames.com and restart.")
            except requests.exceptions.HTTPError as e:
                status = e.response.status_code
                msg = e.response.json().get('status', {}).get('message', e.response.text)
                error = f"{status} {msg}"
    return render_template('index.html', data=data, error=error)

@app.route('/match/<match_id>')
def match_page(match_id):
    try:
        # 4) Fetch full match-V5 details :contentReference[oaicite:7]{index=7}
        full = riot_request(
            f"https://{REGION}.api.riotgames.com"
            f"/lol/match/v5/matches/{match_id}"
        )
        participants = full.get('info', {}).get('participants', [])
    except Exception as e:
        participants = []
        error = str(e)
    else:
        error = None

    return render_template('match_details.html',
                           match_id=match_id,
                           participants=participants,
                           error=error)

if __name__ == '__main__':
    app.run(debug=True)
