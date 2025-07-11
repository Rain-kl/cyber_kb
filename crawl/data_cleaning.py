import pandas as pd


def clean_data():
    # 读取原始数据
    df = pd.read_csv("data/chinacdc_crawl_results.csv")
    print(f"原始数据行数: {len(df)}")
    print("原始数据前5行:")
    print(df.head())

    # 检查数据是否包含 content 列
    if "content" not in df.columns:
        print("错误: 数据中没有找到 'content' 列")
        print(f"可用列: {list(df.columns)}")
        return

    # 删除 content 字数小于 100 的行
    # 首先处理可能的 NaN 值
    df = df.dropna(subset=["content"])

    # 计算每行content的字符数
    df["content_length"] = df["content"].str.len()
    print(f"\ncontent字符数统计:")
    print(df["content_length"].describe())

    # 筛选出字数大于等于100的行
    df_cleaned = df[df["content_length"] >= 200].copy()

    # 删除临时添加的字符数列
    df_cleaned = df_cleaned.drop("content_length", axis=1)

    print(f"\n清洗后数据行数: {len(df_cleaned)}")
    print(f"删除了 {len(df) - len(df_cleaned)} 行content字数小于100的数据")

    # 保存清洗后的数据
    output_file = "data/chinacdc_crawl_results_cleaned.csv"
    df_cleaned.to_csv(output_file, index=False)
    print(f"\n清洗后的数据已保存到: {output_file}")

    # 显示清洗后数据的前几行
    print("\n清洗后数据前5行:")
    print(df_cleaned.head())

    return df_cleaned


if __name__ == "__main__":
    cleaned_data = clean_data()
