import os

def find_images_dirs(root_dir):
    """
    遍历 root_dir 目录下所有子目录，如果目录的最后一级名称为 'images'，则加入列表。
    """
    images_dirs = []
    for current_dir, subdirs, files in os.walk(root_dir):
        # 通过 os.path.basename 获取目录名称
        if os.path.basename(current_dir) == 'images':
            images_dirs.append(current_dir)
    return images_dirs

def main():
    # 请替换为你要搜索的目录
    search_directory = "results_checkpoint-8038"
    # 输出文件名
    output_file = "workspace_dirs.txt"
    
    # 获取所有符合条件的目录
    matching_dirs = find_images_dirs(search_directory)
    matching_dirs = sorted(matching_dirs)
    
    # 写入到TXT文件，每个目录占一行
    with open(output_file, 'w') as f:
        for dir_path in matching_dirs:
            parent_dir = os.path.dirname(dir_path)
            f.write(parent_dir + "/\n")
    
    print(f"共找到 {len(matching_dirs)} 个目录以 'images' 结尾，结果已写入 {output_file}")

if __name__ == '__main__':
    main()