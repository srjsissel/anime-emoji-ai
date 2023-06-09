import os

import argparse
import cv2
import torch
import numpy as np
import glob
from torch.cuda import amp
from tqdm import tqdm

from train import AnimeSegmentation, net_names


def get_mask(model, input_img, use_amp=True, s=640):
    h0, w0 = h, w = input_img.shape[0], input_img.shape[1]
    if h > w:
        h, w = s, int(s * w / h)
    else:
        h, w = int(s * h / w), s
    ph, pw = s - h, s - w
    tmpImg = np.zeros([s, s, 3], dtype=np.float32)
    tmpImg[ph // 2:ph // 2 + h, pw // 2:pw // 2 + w] = cv2.resize(input_img, (w, h)) / 255
    tmpImg = tmpImg.transpose((2, 0, 1))
    tmpImg = torch.from_numpy(tmpImg).unsqueeze(0).type(torch.FloatTensor).to(model.device)
    with torch.no_grad():
        if use_amp:
            with amp.autocast():
                pred = model(tmpImg)
            pred = pred.to(dtype=torch.float32)
        else:
            pred = model(tmpImg)
        pred = pred[0, :, ph // 2:ph // 2 + h, pw // 2:pw // 2 + w]
        pred = cv2.resize(pred.cpu().numpy().transpose((1, 2, 0)), (w0, h0))[:, :, np.newaxis]
        return pred

def main(net='isnet_is', ckpt='saved_models/isnetis.ckpt', data='./inputimage', 
         out='out', img_size=512, device='cuda', fp32=False, only_matted=False):
    device = torch.device(device)

    model = AnimeSegmentation.try_load(net, ckpt, device, img_size=img_size)
    model.eval()
    model.to(device)

    if not os.path.exists(out):
        os.mkdir(out)

    for i, path in enumerate(tqdm(sorted(glob.glob(f"{data}/*.*")))):
        img = cv2.cvtColor(cv2.imread(path, cv2.IMREAD_COLOR), cv2.COLOR_BGR2RGB)
        mask = get_mask(model, img, use_amp=not fp32, s=img_size)
        img = np.concatenate((mask * img + 1 - mask, mask * 255), axis=2).astype(np.uint8)
        img = cv2.cvtColor(img, cv2.COLOR_RGBA2BGRA)
        cv2.imwrite(f'{out}/{i:06d}.png', img)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    # model args
    parser.add_argument('--net', type=str, default='isnet_is',
                        choices=net_names,
                        help='net name')
    parser.add_argument('--ckpt', type=str, default='saved_models/isnetis.ckpt',
                        help='model checkpoint path')
    parser.add_argument('--data', type=str, default='./inputimage',
                        help='input data dir')
    parser.add_argument('--out', type=str, default='out',
                        help='output dir')
    parser.add_argument('--img-size', type=int, default=512,
                        help='hyperparameter, input image size of the net')
    parser.add_argument('--device', type=str, default='cuda',
                        help='cpu or cuda:0')
    parser.add_argument('--fp32', action='store_true', default=False,
                        help='disable mix precision')
    parser.add_argument('--only-matted', action='store_true', default=False,
                        help='only output matted image')

    opt = parser.parse_args()
    print(opt)

    main(opt.net, opt.ckpt, opt.data, opt.out, opt.img_size, opt.device, opt.fp32, opt.only_matted)