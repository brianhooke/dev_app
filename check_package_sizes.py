import os
import sys
import pip

def get_package_size(package_path):
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(package_path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            if not os.path.islink(fp):
                total_size += os.path.getsize(fp)
    return total_size

def main():
    site_packages = next(p for p in sys.path if 'site-packages' in p)
    packages = [p for p in os.listdir(site_packages) if os.path.isdir(os.path.join(site_packages, p))]
    
    package_sizes = {}
    for package in packages:
        package_path = os.path.join(site_packages, package)
        package_size = get_package_size(package_path)
        package_sizes[package] = package_size

    for package, size in sorted(package_sizes.items(), key=lambda item: item[1], reverse=True):
        print(f"{package}: {size / (1024 * 1024):.2f} MB")

if __name__ == "__main__":
    main()
