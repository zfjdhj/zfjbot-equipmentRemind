import asyncio
import json
import os
import time
from typing import Tuple
from .pcrclient import *
import math
from hoshino import *
from nonebot import *
from asyncio import Lock

plugin_path = os.path.dirname(__file__)

client = None
captcha_lck = Lock()
bot = get_bot()
validate = None
acfirst = False
auto_donation = True
sv = Service("zfjbot-equipmentRemind", enable_on_default=False)
HELP_MSG = """invite <13位uid>: 有申请则通过,无申请则邀请
invite check: 查看白名单玩家信息
invite onekeyaccept: 一键通过白名单,无申请则邀请
"""


with open(os.path.join(plugin_path, "equip_data.json"), "rb") as fp:
    equip_data_json = json.load(fp)
    equip_data_dict = {}
    for item in equip_data_json["datas"]:
        equip_data_dict[item["equipmentId"]] = item["equipmentName"]

with open(os.path.join(plugin_path, "account.json")) as fp:
    acinfo = json.load(fp)
    account_json = acinfo


async def captchaVerifier(gt, challenge, userid, account):
    global acfirst
    if not acfirst:
        await captcha_lck.acquire()
        acfirst = True
    url = (
        f"http://pcr.zfjdhj.cn防止腾讯检测/geetest/captcha/?captcha_type=1&challenge={challenge}&gt={gt}&userid={userid}&gs=1"
    )
    reply = f"猫猫({account})遇到了一个问题呢，请完成以下链接中的验证内容后将第一行validate=后面的内容复制，并用指令/pcrval xxxx将内容发送给机器人完成验证\n验证链接：{url}"
    await captcha_lck.acquire()
    await bot.send_private_msg(user_id=acinfo["admin"], message=f"{reply}")
    # 群内通知
    await bot.send_group_msg(group_id=account_json["group_id"], message=f"[CQ:at,qq={account_json['admin']}]\n{reply}")
    return validate


async def errlogger(msg):
    await bot.send_private_msg(user_id=acinfo["admin"], message=f"猫猫登录错误：{msg}")


acinfo_tmp = {
    "account": account_json["farmers"]["acmm"],
    "password": account_json["farmers"]["pwmm"],
    "platform": 2,
    "channel": 1,
}
mbclient = bsdkclient(acinfo_tmp, captchaVerifier, errlogger, account_json["farmers"]["acmm"])
mclient = pcrclient(mbclient)


@sv.on_rex("/pcrval (.*)")
async def validate(bot, ev):
    global validate
    validate = ev["match"].group(1)
    captcha_lck.release()
    await bot.send(ev, f"验证码设置为{validate}")


async def check(client, ev) -> str:
    while client.shouldLogin:
        await client.login()
    if os.path.exists(plugin_path + "/data.json"):
        with open(plugin_path + "/data.json", "rb") as f:
            data_save = json.loads(f.read())
    else:
        data_save = ""
    result = []
    # /clan/info
    data1 = {
        "clan_id": 0,
        "get_user_equip": 1,
        "viewer_id": client.viewer_id,
    }
    res1 = await client.callapi("/clan/info", data1)
    # print("res1:", res1)
    # /clan/chat_info_list
    data2 = {
        "clan_id": res1["clan"]["detail"]["clan_id"],
        "start_message_id": 0,
        "search_date": "2099-12-31",
        "direction": 1,
        "count": 10,
        "wait_interval": 3,
        "update_message_ids": [],
        "viewer_id": client.viewer_id,
    }
    res2 = await client.callapi("/clan/chat_info_list", data2)
    # print("res2:", res2)
    clan_chat_message = res2["clan_chat_message"]
    equip_requests = res2["equip_requests"]
    users = res2["users"]
    # 只统计8小时内的
    for equip_request in equip_requests:
        for chat_message in clan_chat_message:
            if (
                chat_message["message_id"] == equip_request["message_id"]
                and int(time.time()) - int(chat_message["create_time"]) <= 8 * 3600
            ):
                # print(equip_request)
                # print(chat_message["create_time"])
                for user in users:
                    if user["viewer_id"] == chat_message["viewer_id"]:
                        # print(chat_message["viewer_id"], user["name"])
                        result.append(
                            {
                                "viewer_id": equip_request["viewer_id"],
                                "name": user["name"],
                                "equip_id": equip_request["equip_id"],
                                "request_num": equip_request["request_num"],
                                "donation_num": equip_request["donation_num"],
                                "create_time": chat_message["create_time"],
                                "message_id": chat_message["message_id"],
                                "user_donation_num": equip_request["user_donation_num"],
                            }
                        )
    # print(result)
    remind_list = []
    if not ev:
        if data_save != {}:
            for item in result:
                if data_save["users"].get(str(item["viewer_id"])):
                    # 新请求提醒
                    if data_save["users"][str(item["viewer_id"])]["create_time"] != item["create_time"]:
                        remind_list.append(item)
                    # 请求将要结束提醒
                    elif (
                        0 <= item["create_time"] + 8 * 3600 - int(time.time()) <= 15 * 60 and item["donation_num"] < 10
                    ):
                        remind_list.append(item)
                    # 未完成自动捐助
                    elif item["donation_num"] < 10 and auto_donation:
                        remind_list.append(item)
                else:
                    remind_list.append(item)
        else:
            for item in result:
                remind_list.append(item)
    else:
        for item in result:
            if auto_donation:
                if item["donation_num"] < 10:
                    remind_list.append(item)
            else:
                remind_list.append(item)
            # remind_list.append(item)
    for item in result:
        data_save["users"][str(item["viewer_id"])] = item
    # print(remind_list)
    reply = ""
    for i in range(len(remind_list)):
        reply += f"{remind_list[i]['name']}请求装备:{equip_data_dict[remind_list[i]['equip_id']]}\n目前捐助：{remind_list[i]['donation_num']}/{remind_list[i]['request_num']}\n结束时间：{time.strftime('%H:%M:%S',time.localtime(int(remind_list[i]['create_time'])+8*3600))}\n=============="
        if i != len(remind_list) - 1:
            reply += "\n"
    # 写入文件
    with open(plugin_path + "/data.json", "w", encoding="utf8") as f:
        json.dump(data_save, f, ensure_ascii=False)
    print("info: remind_list", remind_list)
    return remind_list, reply


reply = ""


async def equip_main(index, ev, mclient) -> Tuple[int, str]:
    """
    0: success，继续装备捐助
    1: error，暂停装备捐助
    2: info，继续装备捐助
    """
    reply = ""
    equip_requests, equip_req_list = await check(mclient, ev)
    if ev:
        return 0, equip_req_list
    if len(equip_requests) == 0:
        return 2, f"当前暂无装备请求"
    ac = account_json["farmers"][f"ac{index}"]
    pw = account_json["farmers"][f"pw{index}"]
    acinfo_tmp = {
        "account": ac,
        "password": pw,
        "platform": 2,
        "channel": 1,
    }
    bclient = bsdkclient(acinfo_tmp, captchaVerifier, errlogger, ac)
    client = pcrclient(bclient)

    while client.shouldLogin:
        await client.login()
    # 获取今日已捐助数量
    # https://le1-prod-all-gs-gzlj.bilibiligame.net/home/index
    home_index = await client.callapi(
        "/home/index", {"message_id": 1, "tips_id_list": [], "is_first": 1, "gold_history": 0}
    )
    donation_num = home_index["user_clan"]["donation_num"]
    if donation_num == 10:
        return 1, f"今日捐助已达7次或者序列出错"
    equip_requests = (await check(client, ev))[0]
    equip_request = equip_requests[0]
    print(equip_request)
    equip_id = equip_request["equip_id"]
    load_index = await client.callapi("/load/index", {"carrier": "OPPO"})
    current_equip_num = 0
    for item in load_index["user_equip"]:
        if item["id"] == equip_id:
            print(f"{index}当前碎片数量：", item["stock"])
            current_equip_num = item["stock"]
            break
    if not current_equip_num:
        return 1, f"僚机{index}号碎片不足,暂停捐助"
    if current_equip_num < 2:
        return 1, f"僚机{index}号碎片不足2件，暂停捐助"
    user_donation_num = equip_request["user_donation_num"]
    if user_donation_num == 2:
        return 2, f"僚机{index}号已捐助当前装备"
    request = {
        "clan_id": 497375,
        "message_id": equip_request["message_id"],
        "donation_num": 2 - user_donation_num,
        "current_equip_num": current_equip_num,
        "viewer_id": client.viewer_id,
    }
    await client.callapi("/equipment/donate", request)
    reply = f"僚机{index}号捐助2片(剩余{current_equip_num-2})"
    return 0, reply if reply else ""


async def pcrf_equip_check(index: str) -> Tuple[str, str]:
    ac = account_json["farmers"][f"ac{index}"]
    pw = account_json["farmers"][f"pw{index}"]
    acinfo = {
        "account": ac,
        "password": pw,
        "platform": 2,
        "channel": 1,
    }
    bclient = bsdkclient(acinfo, captchaVerifier, errlogger, ac)
    client = pcrclient(bclient)

    while client.shouldLogin:
        await client.login()
    home_index = await client.callapi(
        "/home/index", {"message_id": 1, "tips_id_list": [], "is_first": 1, "gold_history": 0}
    )
    donation_num = home_index["user_clan"]["donation_num"]
    print(f"{index}已捐({donation_num}/10)")
    return index, donation_num


@sv.scheduled_job("interval", minutes=1)
# @sv.scheduled_job("interval", seconds=30)
@sv.on_fullmatch("equip check")
async def equip_check(bot=get_bot(), ev={}):
    global auto_donation, reply, captcha_lck
    while mclient.shouldLogin:
        await mclient.login()
    qq_reply = (await check(mclient, ev))[1]
    if not auto_donation:
        res = await pcrf_equip_check("01")
        if res[1] == 0:
            auto_donation = True
    if auto_donation and qq_reply and not captcha_lck.locked():
        # 获取今日剩余装备可捐数量
        tasks = []
        loop = asyncio.get_event_loop()
        for i in range(1, 8):
            if i < 10:
                index = f"0{i}"
            else:
                index = f"{i}"
            tasks.append(loop.create_task(pcrf_equip_check(index)))
        res = await asyncio.wait(tasks)
        loop.close
        equip_dict = {}
        equip_num = 0
        for item in res[0]:
            equip_num += item.result()[1]
            equip_dict[item.result()[0]] = item.result()[1]
        left_equip_dict_sort = sorted(equip_dict, key=lambda x: equip_dict[x])
        if equip_num == 70:
            today_index = 7
            auto_donation = False
        else:
            today_index = int(math.ceil(equip_num / 10))
            print(left_equip_dict_sort)
            for item in left_equip_dict_sort:
                code, msg = await equip_main(item, ev, mclient)
                if code == 0:
                    print(f"success: {msg}")
                if code == 1:
                    print(f"error: {msg}")
                    auto_donation = False
                    reply += f"\nerror: {msg}"
                    break
                if code == 2:
                    if msg == "当前暂无装备请求":
                        break
                    print(f"info: {msg}")
                if msg != "":
                    reply += f"\ninfo: {msg}"
        print("reply:", reply)
        if reply:
            qq_reply += f"{reply}"
        reply = ""
    if ev:
        auto_donation = False
        code, msg = await equip_main("01", ev, mclient)
        if code == 0:
            qq_reply = msg
        auto_donation = True
        qq_reply = msg
        tasks = []
        loop = asyncio.get_event_loop()
        for i in range(1, 8):
            if i < 10:
                index = f"0{i}"
            else:
                index = f"{i}"
            tasks.append(loop.create_task(pcrf_equip_check(index)))
        res = await asyncio.wait(tasks)
        equip_num = 0
        for item in res[0]:
            # print(item)
            # print(f"{item.result()[0]}已捐({item.result()[1]}/10)")
            equip_num += item.result()[1]
            qq_reply += f"\n僚机{item.result()[0]}号已捐({item.result()[1]}/10)"
        today_index = int(math.ceil(equip_num / 10))
        if captcha_lck.locked():
            qq_reply += f"\n有账号登录失败！！！"
            auto_donation = False
        await bot.send(
            ev,
            f"[CQ:at,qq={account_json['admin']}]\n{qq_reply}\n自动捐助系统：{auto_donation} ({today_index}/7)",
        )
    elif qq_reply:
        qq_reply = f"{qq_reply}\n自动捐助系统：{auto_donation} ({today_index+1  if today_index+1 < 8 else 7}/7)"
        await bot.send_group_msg(group_id=account_json["group_id"], message=qq_reply)
        # await bot.send_group_msg(group_id=618773789, message=qq_reply)
    print(f"自动捐助系统：{auto_donation}")
    await invite_auto(client=mclient)


@sv.on_fullmatch("equip auto")
async def equip_auto_on(bot, ev):
    global auto_donation
    auto_donation = not auto_donation
    await bot.send(ev, f"auto_donation is {auto_donation}")


async def invite_auto(client: pcrclient, bot=get_bot(), ev={}):
    msg = ""
    with open(os.path.join(plugin_path, "account.json")) as fp:
        config_json = json.load(fp)
    white_list = config_json["white_list"]
    while client.shouldLogin:
        await client.login()
    if os.path.exists(plugin_path + "/data.json"):
        with open(plugin_path + "/data.json", "rb") as f:
            data_save = json.loads(f.read())
    else:
        data_save = ""
    # 获取游戏内信息
    clan_info_data = {
        "clan_id": 0,
        "get_user_equip": 1,
        "viewer_id": client.viewer_id,
    }
    clan_info = await client.callapi("/clan/info", clan_info_data)
    member_list = {}
    if clan_info.get("clan"):
        for item in clan_info["clan"]["members"]:
            member_list[item["viewer_id"]] = item["name"]
    clan_join_request_list_data = {
        "clan_id": clan_info["clan"]["detail"]["clan_id"],
        "page": 0,
        "oldest_time": 0,
        "viewer_id": client.viewer_id,
    }
    join_request_list = await client.callapi("/clan/join_request_list", clan_join_request_list_data)
    # print("join_request_list", join_request_list)
    reruest_list = [item["viewer_id"] for item in join_request_list["list"]]

    print(f"info: 入会请求列表{reruest_list}")
    for item in join_request_list["list"]:
        # 自动同意,想要启用自动同意取消注释即可,懒得写开关了
        # if item["viewer_id"] in white_list:
        #     clan_join_request_accept_data = {
        #         "request_viewer_id": item["viewer_id"],
        #         "clan_id": clan_info["clan"]["detail"]["clan_id"],
        #         "viewer_id": client.viewer_id,
        #     }
        #     clan_join_request_accept = await client.callapi("/clan/join_request_accept", clan_join_request_accept_data)
        #     print(f"同意{item['name']}加入公会")
        #     msg+=f"哦,是猫猫的好朋友{item['name']}来了,已自动同意加入公会{clan_info['clan']['detail']['clan_name']}"
        #     request_count-=1
        #     print("clan_join_request_accept", clan_join_request_accept)
        # else:
        # if data_save.get('invite_list'):
        if data_save["invite_list"].get(str(item["viewer_id"])):
            # 有效申请
            print(time.time() - int(data_save["invite_list"][str(item["viewer_id"])]["create_time"]))
            print("is_old", data_save["invite_list"][str(item["viewer_id"])]["old"])
            if (
                time.time() - int(data_save["invite_list"][str(item["viewer_id"])]["create_time"]) < 10 * 60
                or data_save["invite_list"][str(item["viewer_id"])]["old"]
            ):
                data_save["invite_list"][str(item["viewer_id"])]["old"] = False
                msg += f"嗯? {item['name']} 申请加入公会,猫猫要怎么做呢?\nuid:{item['viewer_id']}"
                print("msg:", msg)
        else:
            # 新的申请
            data_save["invite_list"][str(item["viewer_id"])]["old"] = False
            msg += f"嗯? {item['name']} 申请加入公会,猫猫要怎么做呢?\nuid:{item['viewer_id']}"
            data_save["invite_list"][str(item["viewer_id"])] = {"create_time": int(time.time())}
        with open(plugin_path + "/data.json", "w", encoding="utf8") as f:
            json.dump(data_save, f, ensure_ascii=False)
    # 过期申请
    for item in data_save["invite_list"]:
        if item not in reruest_list:
            data_save["invite_list"][item]["old"] = True
    if msg != "":
        msg += f"\n================\ninvite <uid>: 有申请则通过,无申请则邀请"
    if ev:
        await bot.send(ev, f"{msg}", at_sender=True)
    elif msg:
        await bot.send_group_msg(
            group_id=account_json["group_id"], message=f"[CQ:at,qq={account_json['admin']}]\n{msg}"
        )
        # await bot.send_group_msg(group_id=618773789, message=f"[CQ:at,qq={account_json['admin']}]\n{msg}")
    # 自动邀请,鸽了
    return


async def invite(client: pcrclient, uid: str) -> str:
    # 确认正确的uid
    is_accept = False
    res = ""
    # if uid in white_list:
    #     # 同意加入公会
    #     is_accept=True
    # else:
    user_info = await client.callapi(
        "/profile/get_profile", {"target_viewer_id": int(uid), "viewer_id": client.viewer_id}
    )
    # print(user_info)
    if user_info.get("user_info"):
        # print(user_info)
        if user_info["clan_name"] != "":
            res = f"error: {user_info['user_info']['user_name']}已有公会{user_info['clan_name']}"
        else:
            # 同意加入公会
            is_accept = True
    else:
        res = "error: uid有误,请检查后重试"
    # 获取游戏内信息
    clan_info_data = {
        "clan_id": 0,
        "get_user_equip": 1,
        "viewer_id": client.viewer_id,
    }
    clan_info = await client.callapi("/clan/info", clan_info_data)
    if is_accept:
        # 已发起申请
        clan_join_request_list_data = {
            "clan_id": clan_info["clan"]["detail"]["clan_id"],
            "page": 0,
            "oldest_time": 0,
            "viewer_id": client.viewer_id,
        }
        join_request_list = await client.callapi("/clan/join_request_list", clan_join_request_list_data)
        # print("join_request_list", join_request_list)
        is_request = False
        for item in join_request_list["list"]:
            if item == uid:
                is_request = True
                clan_join_request_accept_data = {
                    "request_viewer_id": int(uid),
                    "clan_id": clan_info["clan"]["detail"]["clan_id"],
                    "viewer_id": client.viewer_id,
                }
                clan_join_request_accept = await client.callapi(
                    "/clan/join_request_accept", clan_join_request_accept_data
                )
                res += f"哦,是猫猫的好朋友{user_info['user_info']['user_name']}来了,已同意加入公会{clan_info['clan']['detail']['clan_name']}"
                # print("clan_join_request_accept", clan_join_request_accept)
                break
        # 猫猫进行邀请
        if not is_request:
            clan_info = await client.callapi("/clan/info", clan_info_data)
            member_list = {}
            if clan_info.get("clan"):
                for item in clan_info["clan"]["members"]:
                    member_list[item["viewer_id"]] = item["name"]
            invite_user_list = await client.callapi("/clan/invite_user_list", clan_join_request_list_data)
            # print("invite_user_list", invite_user_list)
            new_invite_user_list = [item["viewer_id"] for item in invite_user_list["list"]]
            # print("new_invite_user_list:", new_invite_user_list)
            if not int(uid) in new_invite_user_list:
                clan_invite_data = {
                    "invited_viewer_id": int(uid),
                    "invite_message": "猫猫邀请您加入公会一起玩耍哦",
                    "viewer_id": client.viewer_id,
                }
                clan_invite = await client.callapi("/clan/invite", clan_invite_data)
                # print("clan_invite:", clan_invite)
                res = f"猫猫已经对{user_info['user_info']['user_name']}发起公会邀请"
            else:
                res = f"猫猫之前已经发起了邀请,但是{user_info['user_info']['user_name']}没有理睬猫猫"
    return res


async def invite_check(client: pcrclient):
    with open(os.path.join(plugin_path, "account.json")) as fp:
        config_json = json.load(fp)
    white_list = config_json["white_list"]
    res = "白名单用户信息:"
    for item in white_list:
        while client.shouldLogin:
            await client.login()
        user_info = await client.callapi(
            "/profile/get_profile", {"target_viewer_id": item, "viewer_id": client.viewer_id}
        )
        if user_info["clan_name"] != "":
            res += f"\n{user_info['user_info']['user_name']}已加入公会：{user_info['clan_name']}"
        else:
            res += f"\n{user_info['user_info']['user_name']}尚未加入任何公会"
    clan_info_data = {
        "clan_id": 0,
        "get_user_equip": 1,
        "viewer_id": client.viewer_id,
    }
    clan_info = await client.callapi("/clan/info", clan_info_data)
    clan_join_request_list_data = {
        "clan_id": clan_info["clan"]["detail"]["clan_id"],
        "page": 0,
        "oldest_time": 0,
        "viewer_id": client.viewer_id,
    }
    join_request_list = await client.callapi("/clan/join_request_list", clan_join_request_list_data)
    # print("join_request_list", join_request_list)
    if len(join_request_list["list"]) > 0:
        res += "\n陌生人信息:"
        for item in join_request_list["list"]:
            res += f"\n{item['name']} uid: {item['viewer_id']}"
    return res


async def invite_onekeyaccept(client: pcrclient):
    with open(os.path.join(plugin_path, "account.json")) as fp:
        config_json = json.load(fp)
    white_list = config_json["white_list"]
    res = "invite 一键邀请:"
    for item in white_list:
        while client.shouldLogin:
            await client.login()
        res += "\n"
        res += await invite(item)
    return res


@sv.on_prefix("invite")
async def invite_main(bot=get_bot(), ev={}):
    args = ev.message.extract_plain_text().split()
    msg = ""
    # user_id = ev.user_id
    is_admin = priv.check_priv(ev, priv.SUPERUSER)
    if len(args) == 0:
        msg = f"猫猫不懂耶~\n可用命令：\n{HELP_MSG}"
    elif len(args) == 1:
        while mclient.shouldLogin:
            await mclient.login()
        if len(args[0]) == 13:
            if is_admin:
                msg = await invite(mclient, args[0])
            else:
                msg = f"猫猫不懂耶~\n可用命令：\n{HELP_MSG}"
        elif args[0] == "check":
            msg = await invite_check(mclient)
            pass
        elif args[0] == "onekeyaccept":
            msg = await invite_onekeyaccept(mclient)
            pass
        else:
            msg = f"猫猫不懂耶~\n可用命令：\n{HELP_MSG}"
    else:
        msg = f"猫猫不懂耶~\n可用命令：\n{HELP_MSG}"
    await bot.send(ev, msg)
    return
