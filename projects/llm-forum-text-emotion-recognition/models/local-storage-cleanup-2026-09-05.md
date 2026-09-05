# 模型副本本地清理记录

日期：2026-09-05

状态：已完成。按用户要求永久删除11个公开原模型或本地MLX转换权重副本，合计 **23,780,592,786 bytes（22.1474 GiB）**。实际目标根目录为 `/Users/phoenix/Assistant/NeuroScience/projects/llm-forum-text-emotion-recognition/models/`。

只删除下表中的权重文件，没有删除目录、tokenizer、config、LICENSE、index、下载记录或原manifest。各manifest继续描述历史完整快照，因此不能仅凭manifest或旧README断言本地权重当前齐全。

## 删除清单

下列路径相对于本models目录；删除前全部逐文件SHA-256核验通过，且为普通文件、无符号链接祖先、无硬链接共享，也未观察到打开句柄。

| 权重文件 | bytes | 删除前SHA-256 |
| --- | ---: | --- |
| `bert-base-cased/snapshot/model.safetensors` | 435755784 | `1d8bdcee6021e2c25f0325e84889b61c2eb26b843eef5659c247af138d64f050` |
| `chinese-roberta-wwm-ext/snapshot/pytorch_model.bin` | 411578458 | `1ded5a5a1c7841dee6e47942f7b5bf2bcf6f73ff19197580f852f7f638f86b35` |
| `qwen3-1.7b-base/mlx-bf16/model.safetensors` | 3441185441 | `aaadb4f90896aef630bca752dcaf0af2192bc95fb273a1202afcd78066dea87a` |
| `qwen3-1.7b-base/upstream/model.safetensors` | 3441185608 | `6df85b39330e5a425ee36253d0f894e4387e4f0a15b9c53cb467d668e6b3a841` |
| `qwen3-1.7b/mlx-bf16/model.safetensors` | 3441185441 | `51dc5e7fe6cade6082d91065daea84fe46522c64e77ecba10a83d5cbd53f66e4` |
| `qwen3-1.7b/upstream/model-00001-of-00002.safetensors` | 3441185608 | `169ad53ec313c3a34b06c0809216e4fc072cce444a5d4ff2b59690d064130ed5` |
| `qwen3-1.7b/upstream/model-00002-of-00002.safetensors` | 622329984 | `912becff8d60672aa8628ef08c05898d9adf17c2ad4ae3caf99b065622fdeff9` |
| `qwen3-4b/upstream/model-00001-of-00003.safetensors` | 3957900840 | `328a91d3122359d5547f9d79521205bc0a46e1f79a792dfe650e99fc2d651223` |
| `qwen3-4b/upstream/model-00002-of-00003.safetensors` | 3987450520 | `6cd087b316306a68c562436b5492edbcf6e16c6dba3a1308279caa5a58e21ca5` |
| `qwen3-4b/upstream/model-00003-of-00003.safetensors` | 99630640 | `e4bf436957184f4eeb86a80e9db394503f1f56446b2e6b7edeac5b81470f4ca1` |
| `twitter-roberta-base/snapshot/pytorch_model.bin` | 501204462 | `3c9cc492ef7a1a9cd3e08dbabce6e8eef942e5d355ffdab19dbfbdd226eb7ae1` |

## 恢复来源

已在删除前核对以下6个固定revision；9个upstream/snapshot权重的远端LFS哈希、文件大小与原manifest一致，下载URL的HEAD均返回200及预期长度。这里只核对元数据，没有重新下载模型。

| 模型 | 原始manifest | 固定版本 |
| --- | --- | --- |
| `Qwen/Qwen3-1.7B` | [manifest](qwen3-1.7b/manifest.json) | [70d244cc86ccca08cf5af4e1e306ecf908b1ad5e](https://huggingface.co/Qwen/Qwen3-1.7B/tree/70d244cc86ccca08cf5af4e1e306ecf908b1ad5e) |
| `Qwen/Qwen3-1.7B-Base` | [manifest](qwen3-1.7b-base/manifest.json) | [ea980cb0a6c2ae4b936e82123acc929f1cec04c1](https://huggingface.co/Qwen/Qwen3-1.7B-Base/tree/ea980cb0a6c2ae4b936e82123acc929f1cec04c1) |
| `Qwen/Qwen3-4B` | [manifest](qwen3-4b/manifest.json) | [1cfa9a7208912126459214e8b04321603b3df60c](https://huggingface.co/Qwen/Qwen3-4B/tree/1cfa9a7208912126459214e8b04321603b3df60c) |
| `cardiffnlp/twitter-roberta-base` | [manifest](twitter-roberta-base/manifest.json) | [cbb417e9647b51504caf68cbe1af6bbf56da06b7](https://huggingface.co/cardiffnlp/twitter-roberta-base/tree/cbb417e9647b51504caf68cbe1af6bbf56da06b7) |
| `google-bert/bert-base-cased` | [manifest](bert-base-cased/manifest.json) | [cd5ef92a9fb2f889e972770a36d4ed042daf221e](https://huggingface.co/google-bert/bert-base-cased/tree/cd5ef92a9fb2f889e972770a36d4ed042daf221e) |
| `hfl/chinese-roberta-wwm-ext` | [manifest](chinese-roberta-wwm-ext/manifest.json) | [5c58d0b8ec1d9014354d691c538661bf00bfdb44](https://huggingface.co/hfl/chinese-roberta-wwm-ext/tree/5c58d0b8ec1d9014354d691c538661bf00bfdb44) |

恢复公开权重时，在对应repo的固定revision下载表中同名文件，放回原子目录，再按原manifest检查大小与SHA-256。不能用仓库main分支的当前权重替代历史revision。

两个1.7B MLX文件需从恢复后的upstream按各自manifest中的conversion.command重新转换，记录环境为mlx 0.32.0、mlx-lm 0.31.3、bfloat16、非量化。没有另存外置二进制副本；重生成后必须验证原哈希，不提前保证字节完全相同。本次是永久删除，不能通过Git或废纸篓直接恢复这些二进制。

## 保留范围与核验

- Qwen3-4B的全部mlx-bf16工件及roberta-base/snapshot保留。
- 所有训练checkpoint、LoRA adapter、分类头、Router参数保留。
- 旧项目experiments、data、forum-topic-emotion-web和SQMA private保留；IAC派生索引与Phase B表征未清理。
- 上述保留范围的8,561个文件，删除前后路径、大小、mtime、inode与链接元数据摘要一致；该检查不是重新读取或哈希私有样本。
- Qwen3-4B原manifest保持3959 bytes，SHA-256为`da447350d9e43213dacc1202da03b50d7e7114b0a4fe2904ff353240b404a641`。
- 本次未修改原实验状态，未做训练、推理或历史实验重跑。

## 空间结果

清理前后`df -k`的可用空间由97,727,596 KiB变为120,957,736 KiB，观察到约22.1540 GiB增加，可用空间约115.35 GiB。同期其他进程与APFS块管理可能造成小幅差异。

旧项目目录账面占用由约60.82 GiB降到38.67 GiB；models目录由约30.18 GiB降到8.03 GiB。需要重新运行依赖已删除权重的1.7B或encoder历史实验时，先按本记录恢复，不能把缺失权重解释为实验结果失效。
