# 卫戍协议助手

《明日方舟》卫戍协议的非官方 Windows 信息查询工具。本版本提供干员、盟约、策略与装备查询，盟约关系图，以及通过截图识别本局禁用盟约的功能。

## 下载和运行

下载仓库中的 `卫戍协议助手-Windows试用版0.2.zip`，完整解压后双击 `GarrisonAssistant.exe`。需要 64 位 Windows，无需安装 Python。详细说明见 `试用版说明.txt`。

支持粘贴或导入完整截图、裁剪后的盟约区域截图；截图须包含全部核心和附加盟约图标，不需要怪物区域。识别结果请核对后确认。

## 源码运行

安装 Python 3.13 及 Pillow、numpy、opencv-python，然后运行 `python app.py`。赛季数据保存在 `season-provisional`，请保持目录结构。

本项目为非官方个人工具，素材和数据来自 [PRTS](https://prts.wiki/)，资料仍需核对。
