import subprocess
import multiprocessing
import os
import torch

torch.set_num_threads(2)
torch.set_num_interop_threads(2)

def run_inference(ws_dir):
    env = os.environ.copy()
    # 限制各个库的线程数
    env["OMP_NUM_THREADS"] = "2"
    env["MKL_NUM_THREADS"] = "2"
    env["NUMEXPR_NUM_THREADS"] = "2"
    env["OPENBLAS_NUM_THREADS"] = "2"
    
    # 运行命令，并等待返回结果
    subprocess.run([
        'python', 'run_particlesfm.py',
        '--workspace_dir', ws_dir,
        '--sfm_type', 'global_theia',
        '--assume_static',
        '--skip_exists'
    ], env=env)

if __name__ == "__main__":
    # 读取所有工作目录（假设存在 workspace_dirs.txt，每行一个目录）
    with open('workspace_dirs_gt.txt', 'r') as f:
        workspace_dirs = [line.strip() for line in f if line.strip()]

    # 创建进程池，限制8个并行进程
    pool = multiprocessing.Pool(processes=8)
    pool.map(run_inference, workspace_dirs)
    pool.close()
    pool.join()