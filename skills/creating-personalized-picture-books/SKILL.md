---
name: creating-personalized-picture-books
description: Use when creating or upgrading a personalized Chinese children's picture book, name-story book, or birthday keepsake from PDFs, illustrations, or a visual reference. 适用于儿童绘本、姓名故事、周岁纪念绘本、角色一致性、图文同生和印刷文件交付。
---

# 个性化绘本制作

把故事、角色和参考落实为完整绘本与可继续制作的源文件。已有PDF、原画和脚本是起点，优先保留质量好的素材。不要只交建议或用进度文档代替制作。

## 锁定当前要求

- 检查实际PDF、原生图像素、脚本、字体与已有检查记录；旧质检不能证明新文件合格。
- 确认年龄、外貌、家庭称谓、姓名意象、纪念场合和已知日期。未知生日不猜测。只问会影响制作且资料无法回答的问题，其余部分继续。
- 按用户最新要求选文字模式：**独立排字**便于准确字号和改字；**图文同生**让中文与水彩画面一起生成。用户明确要求后者时直接执行，同时说明最终图内字是像素，不能冒称逐字可编辑。

## 叙事与角色

按 [references/authoring.md](references/authoring.md) 制作角色卡、动物与礼物规范、逐页脚本。先做代表场景锁定效果，再扩展全书，不必每一页重复请求审批。

保持年龄、脸型、发型、服装轮廓和比例一致。性别识别不足时整体调整用户认可的造型，不能只加发饰。让孩子主动接、摸、看、挥手；礼物从出现到结尾数量与形状连续。姓名解释属于文学联想，未经来源支持不写成字源。

## 插画与标题

用当前环境的图像生成工具修改栅格插画，先看本地参考，明确编辑目标、角色参考和布局参考。保留原场景色彩、构图与水彩质感，精准修改必要部分。

借鉴参考布局，不复制示例人物、文字、红圈、照片背景或水印。童趣标题用清楚、圆润、略有手写变化的字形；小叶、果、羽装饰远离笔画，避免被识别为偏旁。正文落在自然安静的景色中，不自动铺白色文字栏。

保存原生图、提示词、引用及目检记录，将选定文件复制进项目。核对脸、手、动作、礼物及每句中文；每轮修具体问题，默认每项最多两轮，失败保留成功素材并记录限制。扩大像素不能称原生高清。

## 装订与检查

阅读 [references/production-and-qa.md](references/production-and-qa.md)。按实际成品尺寸规划出血和中缝。长文先精简或调布局，不无限缩字；图内字只能估计视觉大小，不能宣称精确pt或字体嵌入。

已有图文一体PNG可用 `scripts/picture_book.py` 装订；它不负责生图或逐字可编辑正文。图内中文用 `scripts/text_check.py` 辅助检查；OCR疑点须看原图，人工复核与当前图像、文案哈希绑定。

检查当前PDF的页数、顺序、裁切、出血、文字安全、实际PPI、色彩状态及可编辑范围。单页与跨页比较应统一裁切原点和像素网格，不能缩放不同大小的栅格来判错位。

交付阅读PDF、顺序单页PDF、内文与封面分件、源文件、素材、角色规范、质量报告和修改记录。区分技术一致性与生产就绪；未达300 PPI或印厂参数未定须保留阻断。数字检查不能证明印厂已签样。

## 随附工具

```text
python scripts/picture_book.py init --project BOOK_DIR
python scripts/picture_book.py export --project BOOK_DIR
python scripts/text_check.py --project BOOK_DIR
python scripts/picture_book.py check --project BOOK_DIR
```

初始化后先填book.json的素材、逐字文案及印厂配置，再生成相应素材。默认24内页、230mm方形、3mm出血，可调整。依赖见scripts/requirements.txt，工程测试见scripts/test_picture_book.py。向外部发布skill或私人项目素材需要用户另行授权，制作任务本身不包含上传许可。
