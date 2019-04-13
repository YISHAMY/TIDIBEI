"""
author: qiuyihao
date: 2019/04/13 - 04-15
description: 单因子测试
"""
import pandas as pd
import numpy as np
import atrader as at
from sklearn import preprocessing
from sklearn import linear_model

# 中位数去极值法
def filter_MAD(df, factor, n=5):
    """
    :param df: 去极值的因子序列
    :param factor: 待去极值的因子
    :param n: 中位数偏差值的上下界倍数
    :return: 经过处理的因子dataframe
    """
    print(df)
    median = df[factor].quantile(0.5)
    new_median = ((df[factor] - median).abs()).quantile(0.5)
    max_range = median + n * new_median
    min_range = median - n * new_median

    for i in range(df.shape[0]):
        print(df.loc[i, factor])
        if df.loc[i, factor] > max_range:
            df.loc[i, factor] = max_range
        elif df.loc[i, factor] < min_range:
            df.loc[i, factor] = min_range
    return df


# 生成起始日期对
def create_date(begin_date, end_date):
    """
    :param begin_date: 开始日期 指明起始年月  如 '2018-01'
    :param end_date: 结束日期 指明结束年月    如 '2018-10'
    :return: 一个起始年月日列表,一个结束年月日列表
     以一个月的第一天和最后一天作为一对日期 如 ['2018-01-01',..] ['2018-01-31',..]
    """
    # 解析字符串
    begin_year = int(begin_date[0:4])
    begin_month = int(begin_date[5:7])
    end_year = int(end_date[0:4])
    end_month = int(end_date[5:7])

    # 待拼接的年日月
    year = begin_year
    month = begin_month

    begin_date_list = []
    end_date_list = []

    big_month = [1, 3, 5, 7, 8, 10, 12]
    small_month = [4, 6, 9, 11]   # 二月另外判断
    while year <= end_year and month <= end_month:
        date_pair = []
        if month >= 10:
            start = str(year) + '-' + str(month) + '-' + '01'
        else:
            start = str(year) + '-0' + str(month) + '-' + '01'
        begin_date_list.append(start)
        end = ''
        # 判断月为大，为小
        if month in big_month:
            end = str(year) + '-' + str(month) + '-' + '31'
        elif month in small_month:
            end = str(year) + '-' + str(month) + '-' + '30'
        elif month == 2:
            if year % 4 == 0 and year % 100 != 0 or year % 400 == 0:
                end = str(year) + '-' + str(month) + '-' + '29'
            else:
                end = str(year) + '-' + str(month) + '-' + '28'

        month += 1
        end_date_list.append(end)
        if month == 13:
            year += 1
            month = 1
    return begin_date_list, end_date_list


# 计算每一个月的单个股票平均收益率
def cal_yield_rate(code, begin_date, end_date):

    """
    :param code: 股票代码
    :param begin_date: K线起始日期，月初
    :param end_date: K线结束日期，月末
    :return: 在该时间内股票的平均收益率
    """
    day_data = at.get_kdata(target_list=[code], frequency='day', fre_num=1, begin_date=begin_date,
                            end_date=end_date, fill_up=False, df=True, fq=1, sort_by_date=True)

    yield_rate = (day_data['close'][len(day_data) - 1] - day_data['close'][0])/day_data['close'][0]
    return yield_rate


# 单因子测试函数
def test_factor(factor, code_list, begin_date_list, end_date_list):
    """
    :param factor:  待测的单因子
    :param code_list : 成分股和权重 如 hs300 code_list = at.get_code_list(block, date=begin_date_list[i])
    :param begin_date_list: 获取每一期因子的开始时间 （12个月，每月一次，从月初开始和月末结束）
    :param end_date_list: 获取每一期因子的结束时间
    :return: 因子的年夏普率，股票总体收益率序列 。。。
    注：使用沪深300股作为测试
    """
    # 记录每一个月的股票池总体收益率
    yield_rate_list = []

    # 记录每一个月股票池各股收益率
    single_yield_rate_list = []

    # 因子每期收益率
    factor_return_list = []

    # 遍历每一期
    for i in range(len(begin_date_list)):

        target_list = code_list['code'].tolist()  # 本月股票池代码
        weight_list = np.array(code_list['weight'].tolist())  # 本月各股票权重
        weight_list = weight_list / weight_list.sum()  # 权重归一化
        weight_list = weight_list.reshape(1, -1)

        # 获取因子月初数据
        print(factor, target_list, begin_date_list[i])
        factor_data = at.get_factor_by_day(factor_list=factor, target_list=target_list,
                                           date=begin_date_list[i])

        # 平均值填充缺失值 中位数去极值 & z-score 规范化
        factor_data = factor_data.fillna(factor_data.mean())
        factor_data = filter_MAD(factor_data, factor, n=5)
        factor_data[factor] = preprocessing.scale(factor_data[factor])
        print(factor_data)
        # 提取因子列，变为np array
        factor_data = np.array(factor_data[factor].tolist()).reshape(1, -1)

        yield_rate = []  # 股票池个股本月平均收益率
        for target in target_list:
            yield_rate.append(cal_yield_rate(target, begin_date_list[i], end_date_list[i]))
        yield_rate = np.array(yield_rate).reshape(1, -1)

        LR = linear_model.LinearRegression()
        LR.fit(factor_data, yield_rate)  # 拟合月初因子和本月平均收益率
        factor_return_list.append(LR.coef_)  # 记录因子收益率

        pred_yield_rate = LR.predict(factor_data)  # 预测的各股票收益率

        single_yield_rate_list.append(list(pred_yield_rate))  # 记录当月各股票收益率

        # 利用权重和个股收益计算股票池整体平均收益率
        mean_yield_rate = (pred_yield_rate * weight_list).sum()

        # 记录当月股票整体平均收益率
        yield_rate_list.append(list(mean_yield_rate))

    # 计算超额收益率
    yield_rate_array = np.array(yield_rate_list)
    over_rate = yield_rate_array - 0.04  # 0.04 代表无风险利率
    # 超额收益率均值和方差
    mean_over_rate = over_rate.mean()
    var_over_rate = over_rate.var()
    # 单位时间夏普率
    sharp_ratio = mean_over_rate / var_over_rate
    # 年化夏普率
    sharp_ratio = np.sqrt(12) * sharp_ratio
    return sharp_ratio, yield_rate_list


factor = ["PE"]
begin_date_list, end_date_list = create_date('2016-01', '2016-12')
A = at.get_code_list('hs300', date='2016-01-01')
sharp_ratio, yield_rate_list = test_factor(factor, A, begin_date_list, end_date_list)
print(sharp_ratio)
print(yield_rate_list)

# 分层回测 todo
# IC，波动率 todo
# 共线性分析 todo





