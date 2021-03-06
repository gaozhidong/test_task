# -*- coding: utf-8 -*-
import base64
import hashlib
import json
import os
import random

import requests
import urllib3
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from requests import utils
from getENV import getENv
from checksendNotify import send

urllib3.disable_warnings()


class Music163CheckIn:
    def __init__(self, check_item):
        self.check_item = check_item
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/84.0.4147.89 Safari/537.36",
            "Referer": "http://music.163.com/",
            "Accept-Encoding": "gzip, deflate",
        }

    @staticmethod
    def _encrypt(key, text):
        backend = default_backend()
        cipher = Cipher(algorithms.AES(key.encode("utf8")), modes.CBC(b"0102030405060708"), backend=backend)
        encryptor = cipher.encryptor()
        length = 16
        count = len(text.encode("utf-8"))
        if count % length != 0:
            add = length - (count % length)
        else:
            add = 16
        pad = chr(add)
        text1 = text + (pad * add)
        ciphertext = encryptor.update(text1.encode("utf-8")) + encryptor.finalize()
        crypted_str = str(base64.b64encode(ciphertext), encoding="utf-8")
        return crypted_str

    def encrypt(self, text):
        return {
            "params": self._encrypt("TA3YiYCfY2dDJQgg", self._encrypt("0CoJUm6Qyw8W8jud", text)),
            "encSecKey": "84ca47bca10bad09a6b04c5c927ef077d9b9f1e37098aa3eac6ea70eb59df0aa28b691b7e75e4f1f9831754919ea784c8f74fbfadf2898b0be17849fd656060162857830e241aba44991601f137624094c114ea8d17bce815b0cd4e5b8e2fbaba978c6d1d14dc3d1faf852bdd28818031ccdaaa13a6018e1024e2aae98844210",
        }

    def login(self, session, phone, password):
        login_url = "https://music.163.com/weapi/login/cellphone"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/84.0.4147.89 Safari/537.36",
            "Referer": "http://music.163.com/",
            "Accept-Encoding": "gzip, deflate",
            "Cookie": "os=pc; osver=Microsoft-Windows-10-Professional-build-10586-64bit; appver=2.0.3.131777; channel=netease; __remember_me=true;",
        }
        hl = hashlib.md5()
        hl.update(password.encode(encoding="utf-8"))
        md5_password = str(hl.hexdigest())
        login_data = self.encrypt(
            json.dumps({"phone": phone, "countrycode": "86", "password": md5_password, "rememberLogin": "true"})
        )
        res = session.post(url=login_url, data=login_data, headers=headers, verify=False)
        ret = res.json()
        if ret["code"] == 200:
            csrf = requests.utils.dict_from_cookiejar(res.cookies)["__csrf"]
            nickname = ret["profile"]["nickname"]
            level_data = self.get_level(session=session, csrf=csrf, login_data=login_data)
            level = level_data["level"]
            now_play_count = level_data["nowPlayCount"]
            next_play_count = level_data["nextPlayCount"]
            now_login_count = level_data["nowLoginCount"]
            next_login_count = level_data["nextLoginCount"]
            return csrf, nickname, level, now_play_count, next_play_count, now_login_count, next_login_count
        else:
            return False, ret.get("message"), 0, 0, 0

    def sign(self, session):
        sign_url = "https://music.163.com/weapi/point/dailyTask"
        res = session.post(url=sign_url, data=self.encrypt('{"type":0}'), headers=self.headers, verify=False)
        ret = res.json()
        if ret["code"] == 200:
            return "?????????????????????+ " + str(ret["point"])
        elif ret["code"] == -2:
            return "????????????????????????"
        else:
            return "????????????: " + ret["message"]

    def task(self, session, csrf):
        url = "https://music.163.com/weapi/v6/playlist/detail?csrf_token=" + csrf
        recommend_url = "https://music.163.com/weapi/v1/discovery/recommend/resource"
        music_lists = []
        res = session.post(
            url=recommend_url, data=self.encrypt('{"csrf_token":"' + csrf + '"}'), headers=self.headers, verify=False
        )
        ret = res.json()
        if ret["code"] != 200:
            print("????????????????????????: ", str(ret["code"]), ":", ret["message"])
        else:
            lists = ret["recommend"]
            music_lists = [(d["id"]) for d in lists]
        music_id = []
        for m in music_lists:
            res = session.post(
                url=url,
                data=self.encrypt(json.dumps({"id": m, "n": 1000, "csrf_token": csrf})),
                headers=self.headers,
                verify=False,
            )
            ret = json.loads(res.text)
            for i in ret["playlist"]["trackIds"]:
                music_id.append(i["id"])
        post_data = json.dumps(
            {
                "logs": json.dumps(
                    list(
                        map(
                            lambda x: {
                                "action": "play",
                                "json": {
                                    "download": 0,
                                    "end": "playend",
                                    "id": x,
                                    "sourceId": "",
                                    "time": 240,
                                    "type": "song",
                                    "wifi": 0,
                                },
                            },
                            random.sample(music_id, 420 if len(music_id) > 420 else len(music_id)),
                        )
                    )
                )
            }
        )
        res = session.post(url="http://music.163.com/weapi/feedback/weblog", data=self.encrypt(post_data))
        ret = res.json()
        if ret["code"] == 200:
            return "??????????????????"
        else:
            return "??????????????????: " + ret["message"]

    def get_level(self, session, csrf, login_data):
        url = "https://music.163.com/weapi/user/level?csrf_token=" + csrf
        res = session.post(url=url, data=login_data, headers=self.headers)
        ret = json.loads(res.text)
        return ret["data"]

    def main(self):
        phone = self.check_item.get("music163_phone")
        password = self.check_item.get("music163_password")
        session = requests.session()
        csrf, nickname, level, now_play_count, next_play_count, now_login_count, next_login_count = self.login(
            session=session, phone=phone, password=password
        )
        res_sign = ""
        res_task = ""
        if csrf:
            res_sign = self.sign(session=session)
            res_task = self.task(session=session, csrf=csrf)
        msg = (
            f"????????????: {nickname}\n????????????: {level}\n??????????????????: {now_play_count}\n"
            f"?????????????????????: {next_play_count - now_play_count}\n?????????????????????: {next_login_count - now_login_count}\n"
            f"????????????: {res_sign}\n????????????: {res_task}"
        )
        return msg


if __name__ == "__main__":
    getENv()
    with open("/ql/config/check.json", "r", encoding="utf-8") as f:
        datas = json.loads(f.read())
    _check_item = datas.get("MUSIC163_ACCOUNT_LIST", [])[0]
    res=Music163CheckIn(check_item=_check_item).main()
    send("???????????????",res)