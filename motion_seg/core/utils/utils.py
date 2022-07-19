﻿# ParticleSfM
# Copyright (C) 2022  ByteDance Inc.

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
import torch
import einops
import cv2
import numpy as np
import torch.nn.functional as F
import os
import yaml
from cvbase.optflow.visualize import flow2rgb

def load_config_file(name):
    cfg = yaml.safe_load(open(name, 'r'))
    class pObject(object):
        def __init__(self):
            pass
    cfg_new = pObject()
    for attr in list(cfg.keys()):
        setattr(cfg_new, attr, cfg[attr])
    return cfg_new

def save_model(model, log_root, epoch, test_iou):
    log_model = os.path.join(log_root, 'checkpoints')
    if not os.path.exists(log_model):
        os.makedirs(log_model)
    filename = os.path.join(log_model, 'checkpoint_{}_iou_{:.2f}.pth'.format(epoch, np.round(test_iou, 3)))
    torch.save({
        'epoch': epoch,
        'model_state_dict': model.state_dict(),
        }, filename)

def set_learning_rate(optimizer, lr):
    for g in optimizer.param_groups:
        g['lr'] = lr


def convert_for_vis(inp, use_flow=False):
    dim = len(inp.size())
    if not use_flow:
        return torch.clamp((0.5*inp+0.5)*255,0,255).type(torch.ByteTensor)
    else:
        if dim == 4:
            inp = einops.rearrange(inp, 'b c h w -> b h w c').detach().cpu().numpy()
            rgb = [flow2rgb(inp[x]) for x in range(np.shape(inp)[0])]
            rgb = np.stack(rgb, axis=0)
            rgb = einops.rearrange(rgb, 'b h w c -> b c h w')
        if dim == 5:
            b, s, w, h, c = inp.size()
            inp = einops.rearrange(inp, 'b s c h w -> (b s) h w c').detach().cpu().numpy()
            rgb = [flow2rgb(inp[x]) for x in range(np.shape(inp)[0])]
            rgb = np.stack(rgb, axis=0)
            rgb = einops.rearrange(rgb, '(b s) h w c -> b s c h w', b=b, s=s)
        return torch.Tensor(rgb*255).type(torch.ByteTensor)

def bb_intersection_over_union(boxA, boxB):
    # determine the (x, y)-coordinates of the intersection rectangle
    xA = max(boxA[0], boxB[0])
    yA = max(boxA[1], boxB[1])
    xB = min(boxA[2], boxB[2])
    yB = min(boxA[3], boxB[3])

    # compute the area of intersection rectangle
    interArea = abs(max((xB - xA, 0)) * max((yB - yA), 0))
    if interArea == 0:
        return 0
    # compute the area of both the prediction and ground-truth
    # rectangles
    boxAArea = abs((boxA[2] - boxA[0]) * (boxA[3] - boxA[1]))
    boxBArea = abs((boxB[2] - boxB[0]) * (boxB[3] - boxB[1]))

    # compute the intersection over union by taking the intersection
    # area and dividing it by the sum of prediction + ground-truth
    # areas - the interesection area
    iou = interArea / float(boxAArea + boxBArea - interArea)

    # return the intersection over union value
    return iou

def heuristic_fg_bg(mask):
    mask = mask.copy()
    h, w = mask.shape
    mask[1:-1, 1:-1] = 0
    borders = 2*h+2*w-4
    return np.sum(mask>0.5)/borders

def rectangle_iou(masks, gt):
    t, s, c, H_, W_ = masks.size()
    H, W = gt.size()
    masks = F.interpolate(masks, size=(1, H, W))
    ms = []
    for t_ in range(t):
        m = masks[t_,0,0] #h w
        m = m.detach().cpu().numpy()
        if heuristic_fg_bg(m) > 0.5: m = 1-m
        ms.append(m)
    masks = np.stack(ms, 0)
    gt = gt.detach().cpu().numpy()
    for idx, m in enumerate([masks[0], masks.mean(0)]):
        m[m>0.1]=1
        m[m<=0.1]=0
        contours = cv2.findContours((m*255).astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[0]
        area = 0
        for cnt in contours:
            (x_,y_,w_,h_) = cv2.boundingRect(cnt)
            if w_*h_ > area:
                x=x_; y=y_; w=w_; h=h_;
                area = w_ * h_
        if area>0:
            bbox = np.array([x, y, x+w, y+h],dtype=float)
            #if the size reference for the annotation (the original jpg image) is different than the size of the mask
            i, j = np.where(gt==1.)
            bbox_gt = np.array([min(j), min(i), max(j)+1, max(i)+1],dtype=float)
            iou = bb_intersection_over_union(bbox_gt,bbox)
        else:
            iou = 0.
        if idx == 0: iou_single = iou
        if idx == 1: iou_mean = iou
    masks = np.expand_dims(masks, 1)
    return masks, masks.mean(0), iou_mean, iou_single

def iou(masks, gt, thres=0.5):
    masks = (masks>thres).float()
    intersect = torch.tensordot(masks, gt, dims=([-2, -1], [0, 1]))
    union = masks.sum(dim=[-2, -1]) + gt.sum(dim=[-2, -1]) - intersect
    return intersect/(union + 1e-12)

def ensemble_hungarian_iou(masks, gt, moca=False):
    thres = 0.5
    b, c, h, w = gt.size()
    gt = gt[0,0,:,:] #h ,w

    if moca:
        #return masks, masks.mean(0), 0, rectangle_iou(masks[0], gt) 
        masks, mean_mask, iou_mean, iou_single_gap = rectangle_iou(masks, gt)
    else:
        masks = F.interpolate(masks, size=(1, h, w))  # t s 1 h w
        mask_iou = iou(masks[:,:,0], gt, thres)  # t s # t s
        iou_max, slot_max = mask_iou.max(dim=1)
        masks = masks[torch.arange(masks.size(0)), slot_max]  # pick the slot for each mask
        mean_mask = masks.mean(0)
        gap_1_mask = masks[0]  # note last frame will use gap of -1, not major.
        iou_mean = iou(mean_mask, gt, thres).detach().cpu().numpy()
        iou_single_gap = iou(gap_1_mask, gt, thres).detach().cpu().numpy()
        mean_mask = mean_mask.detach().cpu().numpy()  # c h w
        masks = masks.detach().cpu().numpy()

    return masks, mean_mask, iou_mean, iou_single_gap


def hungarian_iou(masks, gt):
    thres = 0.5
    masks = (masks>thres).float()
    gt = gt[:,0:1,:,:]
    b, c, h, w = gt.size()
    
    mask = F.interpolate(masks, size=(h, w))
    #IOU
    intersect = (mask*gt).sum(dim=[-2, -1])
    union = mask.sum(dim=[-2, -1]) + gt.sum(dim=[-2, -1]) - intersect
    iou = intersect/(union + 1e-12)
    return iou.mean()

def cls_iou(pred, label):
    thres = 0.5
    mask = (pred>thres).float()
    b, c, n = label.shape 
    # IOU
    intersect = (mask * label).sum(-1)
    union = mask.sum(-1) + label.sum(-1) - intersect
    iou = intersect / (union + 1e-12)
    return iou.mean()

def gt_iou(mask, label, gt):
    # mask: [N, L], label: [N], gt: [H, W, L]
    N, L = mask.shape
    sum_iou = 0
    for i in range(L):
        valid = 1.0 - mask[:,i]
        intersect = (valid * label).sum()
        union = gt[:,:,i].sum()
        if union == 0:
            continue
        iou = intersect / (union+1e-12)
        sum_iou += iou
    mean_iou = sum_iou / L
    return mean_iou

def gt_ratio(mask, label, gt):
    # mask: [N, L], label: [N], gt: [H, W, L]
    N, L = mask.shape
    h, w = gt.shape[0], gt.shape[1]
    sum_ratio = 0
    for i in range(L):
        valid = 1.0 - mask[:,i]
        ratio = valid.sum() / (h*w)
        sum_ratio += ratio
    mean_ratio = sum_ratio / L
    return mean_ratio

TAG_FLOAT = 202021.25

def read_flo(file):
    assert type(file) is str, "file is not str %r" % str(file)
    assert os.path.isfile(file) is True, "file does not exist %r" % str(file)
    assert file[-4:] == '.flo', "file ending is not .flo %r" % file[-4:]
    f = open(file,'rb')
    flo_number = np.fromfile(f, np.float32, count=1)[0]
    assert flo_number == TAG_FLOAT, 'Flow number %r incorrect. Invalid .flo file' % flo_number
    w = np.fromfile(f, np.int32, count=1)
    h = np.fromfile(f, np.int32, count=1)
    data = np.fromfile(f, np.float32, count=2*w[0]*h[0])
    # Reshape data into 3D array (columns, rows, bands)
    flow = np.resize(data, (int(h), int(w), 2))
    f.close()
    return flow

def save_img_pred_gt_horizon(path, idx, img, pred, gt):
    # img: [N, H, W, 3], pred & GT: [N, H, W] 
    n, h, w, _ = img.shape
    img = np.reshape(np.transpose(img, (1,0,2,3)), (h, n*w, 3))
    pred = np.reshape(np.transpose(pred > 0.5, (1,0,2)), (h, n*w))
    gt = np.reshape(np.transpose(gt, (1,0,2)), (h, n*w))
    cv2.imwrite(os.path.join(path, "{:0>6d}_img.png".format(idx)), 255.0*img)
    cv2.imwrite(os.path.join(path, "{:0>6d}_pred.png".format(idx)), 255.0*pred)
    cv2.imwrite(os.path.join(path, "{:0>6d}_gt.png".format(idx)), 255.0*gt)


color_bank = [(255,0,0), (0,255,0), (0,0,255), (255,255,0), (255,0,255), (0,255,255)]


def draw_traj_cls(img, traj, mask, label, gt_label):
    # img: [L, H, W, 3], traj: [N, L, 2], mask: [N, L], label: [N]
    L, h, w, _ = img.shape
    N = traj.shape[0]
    vis_imgs = [img[i][:,:,::-1].copy() for i in range(L)]
    gt_imgs = [img[i][:,:,::-1].copy() for i in range(L)]
    traj_imgs = [img[i][:,:,::-1].copy() for i in range(L)]
    for i in range(N):
        single_traj = traj[i]
        single_mask = mask[i]
        for j in range(L):
            if single_mask[j] != 1:
                x, y = single_traj[j]
                x, y = int(x), int(y)
                l = int(label[i] > 0.5)
                gt_l = int(gt_label[i] > 0.5)
                color = color_bank[l]
                gt_color = color_bank[gt_l]
                cv2.circle(vis_imgs[j], center=(x,y), radius=1, color=color, thickness=2)
                cv2.circle(gt_imgs[j], center=(x,y), radius=1, color=gt_color, thickness=1)
    for i in range(100):
        idx = np.random.randint(N)
        single_traj = traj[idx]
        single_mask = mask[idx]
        for j in range(L):
            if single_mask[j] != 1:
                x, y = single_traj[j]
                x, y = int(x), int(y)
                cv2.circle(traj_imgs[j], center=(x,y), radius=3, color=color_bank[idx%6], thickness=4)
    vis_imgs = np.concatenate(vis_imgs, axis=1)
    gt_imgs = np.concatenate(gt_imgs, axis=1)
    traj_imgs = np.concatenate(traj_imgs, axis=1)
    concat_imgs = np.concatenate([img[i][:,:,::-1].copy() for i in range(L)], axis=1)
    combine_imgs = np.concatenate([concat_imgs, vis_imgs, gt_imgs, traj_imgs], 0)
    return combine_imgs
    
