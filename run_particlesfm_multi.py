import subprocess
import multiprocessing

def run_inference(ws_dir):
    # 运行命令，并等待返回结果
    subprocess.run([
        'python', 'run_particlesfm.py',
        '--workspace_dir', ws_dir,
        '--sfm_type', 'global_theia',
        '--assume_static'
    ])

if __name__ == "__main__":
    # 读取所有工作目录（假设存在 workspace_dirs.txt，每行一个目录）
    with open('workspace_dirs.txt', 'r') as f:
        workspace_dirs = [line.strip() for line in f if line.strip()]

    # 创建进程池，限制10个并行进程
    pool = multiprocessing.Pool(processes=20)
    pool.map(run_inference, workspace_dirs)
    pool.close()
    pool.join()