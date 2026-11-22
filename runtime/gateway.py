"""Provider presets and non-billable connection discovery. Secrets never leave this module as API data."""
import json
import os
import time
import urllib.error
import urllib.request
from credentials import read_key

PROVIDERS = [
    {"id":"custom","name":"自定义兼容接口","base_url":"https://api.openai.com/v1","key_env":"MANJU_API_KEY","text_model":"gpt-4.1-mini","image_model":""},
    {"id":"openai","name":"OpenAI","base_url":"https://api.openai.com/v1","key_env":"OPENAI_API_KEY","text_model":"gpt-4.1-mini","image_model":""},
    {"id":"deepseek","name":"DeepSeek","base_url":"https://api.deepseek.com/v1","key_env":"DEEPSEEK_API_KEY","text_model":"deepseek-flash","image_model":""},
    {"id":"dashscope","name":"阿里云百炼（文本）","base_url":"https://dashscope.aliyuncs.com/compatible-mode/v1","key_env":"DASHSCOPE_API_KEY","text_model":"qwen-plus","image_model":""},
    {"id":"ark","name":"火山方舟（自定义接入点）","base_url":"https://ark.cn-beijing.volces.com/api/v3","key_env":"ARK_API_KEY","text_model":"","image_model":""},
]
PROVIDERS += [
    {"id":"moonshot","name":"Kimi / Moonshot","base_url":"https://api.moonshot.cn/v1","key_env":"MOONSHOT_API_KEY","text_model":"","image_model":""},
    {"id":"zhipu","name":"智谱 GLM","base_url":"https://open.bigmodel.cn/api/paas/v4","key_env":"ZHIPU_API_KEY","text_model":"","image_model":""},
    {"id":"minimax","name":"MiniMax（文本兼容）","base_url":"https://api.minimaxi.com/v1","key_env":"MINIMAX_API_KEY","text_model":"","image_model":""},
    {"id":"gemini","name":"Google Gemini（文本兼容）","base_url":"https://generativelanguage.googleapis.com/v1beta/openai","key_env":"GEMINI_API_KEY","text_model":"","image_model":""},
]
KEY_NAMES={p["key_env"] for p in PROVIDERS}|{"VOLCENGINE_API_KEY"}


def api_key(config, root=None):
    key_name=config.get("key_env","MANJU_API_KEY")
    if key_name not in KEY_NAMES:
        return None
    return read_key(root,key_name) or os.environ.get(key_name) or None


def profiles(root=None):
    return [{**p,"key_available":bool(api_key(p,root)),"key_source":"encrypted" if read_key(root,p["key_env"]) else "environment" if os.environ.get(p["key_env"]) else "missing"} for p in PROVIDERS]


def auto_settings(existing, root=None):
    # Never send a key discovered for one provider to a different provider's endpoint.
    ordered=sorted(PROVIDERS,key=lambda p:p["id"]!=existing.get("provider","custom"))
    chosen=next((p for p in ordered if api_key(p,root)),None)
    if not chosen:
        return {**existing,"remote_enabled":False}, {"connected":False,"mode":"local","message":"未检测到可用密钥。已启用本地剧本、规则提取、中文配音与 FFmpeg 样片流程。","models":[]}
    image_fields={}
    if existing.get('image_model') and not existing.get('image_provider_url'):
        image_fields=dict(image_provider=existing.get('provider','custom'),image_provider_url=existing['provider_url'],image_key_env=existing.get('key_env','MANJU_API_KEY'))
    config={**existing,**image_fields,"provider":chosen["id"],"key_env":chosen["key_env"],"provider_url":chosen["base_url"],
            "text_model":chosen["text_model"],"image_model":existing.get("image_model",""),"remote_enabled":False}
    if chosen["id"]=="custom":
        for key in ("provider_url","text_model","image_model"):
            config[key]=existing.get(key,config[key])
    return config,None


def probe(config, root=None):
    secret=api_key(config,root)
    if not secret:
        return {"connected":False,"mode":"local","models":[],"message":"尚未配置当前供应商密钥。可在模型中心加密保存 API Key，或使用服务端环境变量。"}
    start=time.monotonic()
    request=urllib.request.Request(config["provider_url"].rstrip("/")+"/models",headers={"Authorization":"Bearer "+secret,"Accept":"application/json"})
    try:
        with urllib.request.urlopen(request,timeout=15) as response:
            content=response.read(2*1024*1024)
        value=json.loads(content)
        if not isinstance(value,dict) or not isinstance(value.get("data"),list):
            raise ValueError("incompatible model catalog")
        models=[str(m["id"]) for m in value.get("data",[]) if isinstance(m,dict) and m.get("id")]
        return {"connected":True,"mode":"provider","models":models[:500],"latency_ms":round((time.monotonic()-start)*1000),
                "message":f"兼容接口连接成功，获取 {len(models)} 个模型。此检测不调用付费生成接口。"}
    except urllib.error.HTTPError as exc:
        code=exc.code;exc.close()
        reason={401:"密钥无效或未授权",403:"账号无权限",404:"服务未开放 /models，请核对 Base URL 或手填模型",429:"供应商限流，请稍后重试"}.get(code,"请核对接口与账号状态")
        return {"connected":False,"mode":"provider","models":[],"message":f"HTTP {code}：{reason}"}
    except (OSError,ValueError):
        return {"connected":False,"mode":"provider","models":[],"message":"连接未确认：网络不可达、超时或响应格式不兼容；未发送付费生成请求。"}
