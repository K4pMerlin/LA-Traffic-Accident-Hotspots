# 原始数据

下载 US Accidents 的七个 Parquet 分片，放到本目录。文件名应符合 `train-*-of-*.parquet`，当前版本合计 7,728,394 行。Notebook 会核对分片数量、字段结构及哈希。[原始数据集](https://huggingface.co/datasets/yuvidhepe/us-accidents-updated/tree/main)

清洗后的数据使用单独的共享数据仓库或本地运行目录。当前代码仓库尚未配置清洗数据下载地址，拿到组内链接后可更新此处。原始数据与清洗数据的许可和署名要求以相应数据来源为准，代码仓库的 LICENSE 用于项目代码。
