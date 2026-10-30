# 导出、文字复核与印刷验收

## 装订工具

依赖：`python -m pip install -r scripts/requirements.txt`。OCR另外需要rapidocr_onnxruntime。

```text
python scripts/picture_book.py init --project BOOK_DIR --interior-pages 24
python scripts/picture_book.py export --project BOOK_DIR
python scripts/text_check.py --project BOOK_DIR
python scripts/picture_book.py check --project BOOK_DIR
```

book.json参数是方形成品trim_mm=230、bleed_mm=3、safe_mm=14。artwork依阅读序列列出id/kind/file/expected_text：front、P01、spread_01…、P24、back。kind为single或spread，素材放项目assets。expected_text每条是一行应印文字，涵盖正文、姓名标题、礼物标签和祝愿，不加入未印分镜说明。

默认24内页：P01独立右页，P02–23为11跨页，P24独立左页；合并单页26页，预览15画布。其他偶数页数按同一首尾规则。工具输出print.pdf、interior_print.pdf、covers_print.pdf、preview.pdf和qa/export_manifest.json；仅页码为10pt独立嵌入文字，不把图中文字转成字体。

## 分辨率与出血

有效PPI由实际像素/放置英寸决定。裁切看不见的部分不会增加原生细节；放大后写300DPI元数据也不合格。有重采样须记录原图尺寸与处理，不能只查放大后文件。

1774×887放到472×236mm约95.47PPI；1254方图放到236mm约134.96PPI。230mm成品加3mm出血，300PPI约需2788方图，展开约5575×2788。这是尺寸计算，不是生图工具保证值。

独立排字初始建议正文15–18pt、行距1.4–1.6，标题28–44pt，页码9–11pt，按尺寸、文长、参考调整。图内字只能估计，不能承诺精确pt；独立文字查真实轮廓、缺字与嵌入。装饰也要避裁切线。

裁切和出血框须真实存在。默认每边3mm，文字与主要人物按约定安全区避边和书脊。特殊内侧出血、硬壳包边、圆角和书脊按印厂模板重设。顺序单页不是印厂拼版，两张封面不是完整精装包壳。

## OCR及人工复核

text_check.py保存识别框、置信度、预期文案、源图和文案哈希。逐句与字频同时比较，避免字数相同但乱序通过；标点另报。未填expected_text不算通过。

疑点查看原图，记录文字、结论、源图SHA和文案SHA。任一变更使旧复核失效。不要为迎合OCR改正确人名；若决定改文案，同步脚本和重新检查。

人工记录写入qa/text_review.json的reviews数组，每图一条：id、image_sha256、expected_text_sha256、visual_review_completed=true、confirmed_text_error=false。两个哈希应采用text_check.py输出；另记录具体检查结论。确为无字页时额外声明wordless=true，不把尚未填写文案当作无字设计。全局in_image_text_reviewed只有在逐图当前记录齐全后才可打开。check会重新核对哈希，不能靠全局开关绕过。

检测框换成毫米后分别分配到左右成品页，测外缘和中缝。草地误识成文字的假框可人工排除，但保留原OCR和分类证据；不以一个全局“已检查”替代逐项证据。

## 当前PDF和生产状态

核对当前页序、MediaBox/TrimBox/BleedBox、字体、实际图像矩阵与源哈希。跨导出比较先把裁切移至同一原点，直接渲染到相同像素网格；不同取整栅格再resize可能把正确页面误判为错位。

check成功只是所填标准和参数下的数字预检。只有当前文字已复核、印厂配置确认、实际PPI达标且技术一致时才可通过；修改图或PDF后重跑。色彩说明字符串不是ICC转换，不据此声称CMYK/PDF-X。实体签样与最终生产仍由印厂确认。

质量报告逐项列通过、未通过、未检查及原因，注明文字模式、可编辑范围、原生PPI和待定印厂项。成品、源图、脚本、角色卡和修改记录都须实际存在。ZIP关闭写句柄后重新打开校验完整性。
