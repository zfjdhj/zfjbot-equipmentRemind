# zfjbot-equipmentRemind

a plugin for hoshino

## 使用

1. 抓包或者使用冲冲大佬的[工具](https://github.com/qq1176321897/pcrjjc2)获取登录信息。
2. 将信息填入`account.json`,没有的话就目录下新建一个。
其中`group_id`为要推送消息的群。

```json
//account.json
{
    "uid": "output.txt中的uid_long，数字格式",
    "access_key": "output.txt中的access_token",
    "platform": 2,
    "channel": 1,
    "group_id": 1234567
}
```

## 返回数据

``` json
{
    "users":[
        {
            "viewer_id": 1167771312319,
            "name": "纸飞机",
            "equip_id": 124523,
            "request_num": 10,
            "donation_num": 10,
            "create_time":12121212,
            "is_remind":False
        }
    ],
}
```

## 感谢

部分代码参考：

<https://github.com/qq1176321897/pcrjjc2>

<https://github.com/infinityedge01/qqbot2>