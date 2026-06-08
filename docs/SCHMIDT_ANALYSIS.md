# SVD/K 算法

## Raw-Aligned Schmidt-like K

对 JTI 矩阵 `H` 计算 Schmidt-like 有效模数：

```
P = H / sum(H)          # 归一化为概率矩阵
A = sqrt(P)             # 取平方根
s = SVD(A)              # 奇异值分解
lambda_n = s_n^2 / sum(s_n^2)  # 特征值权重
K = 1 / sum(lambda_n^2)        # 有效模数（purity 的倒数）
```

## 解释

- **K = 1**：纯态（单个 bin 占主导）
- **K = dim**：完全混合（所有 bin 均匀分布）
- **K 越大**：联合到达时间结构越丰富
- **purity** = `1/K`：分布的集中度

## lambda 分布

- `lambda1`：第一主成分权重，越大说明 JTI 越集中
- `lambda5_cumsum`：前 5 个主成分累积贡献，越高说明有效自由度越少
- `lambda10_cumsum`：前 10 个主成分累积贡献

## 注意事项

- K 是 shape 参数，依赖于 binwidth 和 dimension
- 20 ps binwidth 可能低于 detector jitter，属于 oversampling
- 建议在 bw=40-50 ps 区间内考察 K 的稳定性
- 不同 frame_period（不同 N）下 K 不直接可比
