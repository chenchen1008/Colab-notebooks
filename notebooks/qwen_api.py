# OpenAI 兼容代理：把 ComfyUI 的 Qwen-Image 2.1 工作流包装成 /v1/images/generations
# 节点结构按 ComfyUI 官方 image_qwen_image_2_1_t2i 工作流 + ComfyUI-GGUF 修正：
#   UnetLoaderGGUF / CLIPLoader(type=qwen_image) / VAELoader
#   TextEncodeQwenImage21（同时输出 positive / negative / 64 通道空 latent）
#   KSampler / VAEDecode / SaveImage
from fastapi import FastAPI
from pydantic import BaseModel
import requests, base64, uuid, time, uvicorn, traceback

app = FastAPI(title='Qwen-Image-2.1-Turbo proxy')
COMFY = 'http://127.0.0.1:8188'
UNET = 'qwen-image-2.1-turbo-Q4_K_M.gguf'
CLIP = 'qwen3vl_8b_int8_convrot.safetensors'
VAE = 'qwen_image_2.1_vae_bf16.safetensors'
UNET_CLASS = 'UnetLoaderGGUF'

class ImageGenRequest(BaseModel):
    prompt: str
    model: str = UNET
    width: int = 1024
    height: int = 1024
    steps: int = 8
    seed: int = -1
    cfg: float = 1.0
    negative_prompt: str = ''

@app.get('/')
def root():
    return {'status': 'ok', 'backend': COMFY, 'endpoint': '/v1/images/generations'}

@app.get('/health')
def health():
    try:
        requests.get(COMFY + '/system_stats', timeout=5).raise_for_status()
        return {'ok': True, 'comfyui': 'up'}
    except Exception as e:
        return {'ok': False, 'comfyui': repr(e)}

@app.get('/v1/models')
def models():
    return {'object': 'list', 'data': [{'id': UNET, 'object': 'model'}]}

def build_workflow(req: ImageGenRequest):
    seed = req.seed if req.seed and req.seed >= 0 else uuid.uuid4().int >> 64
    # Qwen-Image 2.1 的 latent 是 64 通道、边长 /16，由 TextEncodeQwenImage21 生成，
    # 不能用 EmptyLatentImage（那是 4 通道、边长 /8 的老格式）。
    # 该节点无参考图时输出正方形 latent，边长由 resolution 决定。
    resolution = max(32, (max(req.width, req.height) // 32) * 32)
    return {
        '1': {'inputs': {'unet_name': req.model}, 'class_type': UNET_CLASS},
        '2': {'inputs': {'clip_name': CLIP, 'type': 'qwen_image'}, 'class_type': 'CLIPLoader'},
        '3': {'inputs': {'vae_name': VAE}, 'class_type': 'VAELoader'},
        '4': {'inputs': {
            'clip': ['2', 0],
            'prompt': req.prompt,
            'negative_prompt': req.negative_prompt,
            'vae': ['3', 0],
            'resolution': resolution,
        }, 'class_type': 'TextEncodeQwenImage21'},
        '5': {'inputs': {
            'model': ['1', 0],
            'positive': ['4', 0],
            'negative': ['4', 1],
            'latent_image': ['4', 2],
            'seed': int(seed),
            'steps': req.steps,
            'cfg': req.cfg,
            'sampler_name': 'euler',
            'scheduler': 'normal',
            'denoise': 1.0,
        }, 'class_type': 'KSampler'},
        '6': {'inputs': {'samples': ['5', 0], 'vae': ['3', 0]}, 'class_type': 'VAEDecode'},
        '7': {'inputs': {'images': ['6', 0], 'filename_prefix': 'qwen_colab'}, 'class_type': 'SaveImage'},
    }

@app.post('/v1/images/generations')
def generate(req: ImageGenRequest):
    try:
        r = requests.post(COMFY + '/prompt', json={'prompt': build_workflow(req)}, timeout=30)
        if r.status_code != 200:
            return {'error': 'comfyui /prompt rejected', 'detail': r.text[:1500]}
        pid = r.json()['prompt_id']
        outs = None
        for _ in range(240):
            time.sleep(2)
            h = requests.get(COMFY + f'/history/{pid}', timeout=10).json()
            if pid in h and 'outputs' in h[pid]:
                outs = h[pid]['outputs']
                break
            if pid in h and h[pid].get('status', {}).get('status_str') == 'error':
                return {'error': 'comfyui execution error', 'detail': str(h[pid].get('status'))[:1500]}
        if outs is None:
            return {'error': 'generation timeout'}
        images = []
        for node_id, out in outs.items():
            for img in out.get('images', []):
                data = requests.get(COMFY + '/view',
                    params={'filename': img['filename'], 'subfolder': img.get('subfolder', ''), 'type': 'output'},
                    timeout=60).content
                images.append({'b64_json': base64.b64encode(data).decode('ascii')})
        if not images:
            return {'error': 'no images in output', 'detail': str(outs)[:1500]}
        return {'created': int(time.time()), 'data': images}
    except Exception:
        return {'error': 'proxy exception', 'detail': traceback.format_exc()[-1500:]}

if __name__ == '__main__':
    print('qwen_api: listening on 0.0.0.0:8010 -> ' + COMFY, flush=True)
    uvicorn.run(app, host='0.0.0.0', port=8010, log_level='info')
