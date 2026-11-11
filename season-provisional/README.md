# 卫戍协议·规程：资料包（待人工核对）

来源：PRTS「卫戍协议·规程/PRTS盟约记录」，保留原始页面用于复核。

`season.sqlite3` 中：
- `operators`：按网页行记录的干员，`names_json` 保留预设及原型名称和头像网址；一行不一定等于一个独立干员。
- `operator_bonds`：干员行与盟约的关系。
- `bonds`：盟约名称、类别、效果和图片网址。
- `trait_icons`：特质类别和对应图标网址。
- `images`：图片网址与本地 `images/` 文件的映射。
- `strategies`、`equipment`：策略和装备的名称、效果等初步提取字段；装备详情可能同时包含背景文案。
- `entries`：策略及装备原始表格文本和 HTML，可用于核对提取结果。
- `records`、`assets`：原始网页分段和图片引用存档。

提取结果尚需人工核对，特别是预设/原型的对应、特质的普通/精锐效果、盟约描述中的术语注释，以及策略和装备表格。图片只检查了文件头，未逐张目视检查。截图识别模板尚未加入。

部分干员的网页特质只有一段，空白的第二段不代表提取失败。相同原型可能出现在多条不同记录中，不能仅用原型名称合并记录。

基础检查可在项目根目录运行 `python validate_season.py`；资料重建顺序是 `python build_data.py`、`python extract_season.py`、`python extract_entries.py`、`python download_bond_originals.py`、`python download_trait_icons.py`。后四步涉及素材下载。
