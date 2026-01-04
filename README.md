# 部署教程

## 获取代码文件

（老师可能会提供源代码压缩包吧 XD）

可以通过 `git` 获取源代码。在安装了 `Git` 的情况下，使用
```bash
git clone https://github.com/Arccosnsx/MultiModalDocSystem.git
```
获取最新代码版本。如果我有空的话，会进一步完善这个流水线。

## 后端

### Python

本项目在 Python 3.11 + CUDA 12.6 上通过测试。我推荐使用 Python 虚拟环境。假设目前在 `MultiModalDocSystem`文件夹下，在终端输入以下命令：

```bash
cd ./backend
python -m venv .venv
source ./.venv/Script/activate
```
创建并激活虚拟环境，然后执行
```bash
pip install -r requirements.txt
```
安装依赖。安装完毕后，执行 `web_api.py` 即可启动后端服务

*需要注意的是，以上命令如果在 Windows 下执行，可能需要 bash 环境*

执行后，正常情况下应该会自动下载 PaddleOCR 的模型。如果报错，请自行查看 PaddleOCR 文档。

### Ollama

Ollama 本地部署可以参考 https://docs.ollama.com/

## 前端

前端基于 Node.js 以及 npm 部署。因此需要先安装这两项，参考 https://nodejs.org/zh-cn 。我使用的版本是 `Node.js v22.14.0` + `npm v11.2.0`

假设目前在 `MultiModalDocSystem`文件夹下，在终端输入以下命令安装依赖：

```bash
cd ./frontend
cd ./MultiModalDocSystem
npm install
```

然后使用
```bash
npm run dev
```
启动开发模式。其他模式配置需要自己写。

值得注意的是，如果前后端并没有部署到同一个服务器上（或者是使用` docker `部署 `node.js` 时），可能存在请求跨域问题。这一点需要服务器防火墙与 `npm` 配置相配合。