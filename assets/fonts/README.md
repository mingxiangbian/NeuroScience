# Self-hosted Chinese calligraphy font subsets

These files are small `woff2` subsets for the `papers/` homepage.

- `MaShanZheng-WenXianGe.woff2`
  - Source font: Ma Shan Zheng
  - Upstream: https://github.com/google/fonts/tree/main/ofl/mashanzheng
  - License: SIL Open Font License, Version 1.1
  - Included text: `文献阁`
- `ZhiMangXing-Bookmark.woff2`
  - Source font: Zhi Mang Xing
  - Upstream: https://github.com/google/fonts/tree/main/ofl/zhimangxing
  - License: SIL Open Font License, Version 1.1
  - Included text: `记忆与智能体`

Subset generation intent:

```sh
pyftsubset MaShanZheng-Regular.ttf --text='文献阁' --flavor=woff2
pyftsubset ZhiMangXing-Regular.ttf --text='记忆与智能体' --flavor=woff2
```

Do not commit the full upstream `.ttf` files here; keep only page-specific subsets.
