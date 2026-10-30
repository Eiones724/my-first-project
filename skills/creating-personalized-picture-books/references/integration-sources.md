# 方法来源与适配范围

整合核查日期：2026-10-30。技能版本1.1.0；沿用schema_version=1的装订数据和原脚本，不新增生图SDK依赖。未来核查仓库维护情况时看实际提交与发布记录，不能用updated_at代替代码更新时间。

## 近期来源

参考 [make-kids-picturebooks](https://github.com/yakamoz203123-cloud/make-kids-picturebooks/tree/4d8ba12ac2eb67196a6d25b1da27f9e421027c3b)，锁定提交4d8ba12ac2eb67196a6d25b1da27f9e421027c3b（2026-10-27）：

- [故事设计](https://github.com/yakamoz203123-cloud/make-kids-picturebooks/blob/4d8ba12ac2eb67196a6d25b1da27f9e421027c3b/references/story-design.md)：先故事再分页、以可见行动和变化推动情绪回报。
- [生产流程](https://github.com/yakamoz203123-cloud/make-kids-picturebooks/blob/4d8ba12ac2eb67196a6d25b1da27f9e421027c3b/references/production-workflow.md)：信息职责分明、最小续做上下文、前后页状态与局部失效。

上述方法经重新组织，适配姓名、生日和家庭纪念故事；保留感官参与和亲人回应，不要求所有作品具有科学命题或两轮失败。不移植上游队列代码、逐页新授权、固定画布、时限、角色资产、字体、知识验证器或默认pure-images交付。

此前调研的weaiw、SensationHeal、lxylouis、weivea、jingk1012-ux等仓库未作为本次代码或文档移植来源，其旧供应商接口不构成本技能依赖。电子阅读或TTS仅在有实际需求时另行适配当前工具。

## 官方规范

按 [OpenAI技能规范](https://learn.chatgpt.com/docs/build-skills) 保留简短入口与按需参考；按 [模型说明](https://learn.chatgpt.com/docs/models) 与 [图像生成文档](https://developers.openai.com/api/docs/guides/image-generation) 区分主模型与图像工具。上述链接用于需要时重新核查，不是某型号的实测凭证。

## 上游许可证声明

保留所参考方法来源的MIT声明；未复制其字体和任何私人素材。原文见 [LICENSE](https://github.com/yakamoz203123-cloud/make-kids-picturebooks/blob/4d8ba12ac2eb67196a6d25b1da27f9e421027c3b/LICENSE)。此声明只说明上游许可，不声称拥有用户资料的公开发布权。

```text
MIT License

Copyright (c) 2026 make-kids-picturebooks contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

Third-party exception: assets/kidsbook-print.ttf is a modified Noto Sans CJK
font, copyright Adobe, distributed under SIL OFL 1.1 rather than MIT.
Its license and provenance are in assets/font-license.txt and
assets/font-provenance.json. This software license grants no rights to
user-supplied books, references, or generated project assets.
```
