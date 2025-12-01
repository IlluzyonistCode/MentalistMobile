import os
import sys
import subprocess
import shutil
import re
from pathlib import Path
from colorama import Fore, Style, init

init(autoreset=True)

PROJECT_DIR = 'com.werewolfapps.online'
NEW_PACKAGE_NAME = 'com.mentalist.mobile'
OLD_APP_NAME = 'Wolvesville'
NEW_APP_NAME = 'Mentalist'
CUSTOM_ICON_PATH = 'mentalist-mobile.png'
NEW_SPLASH_COLOR = '#000000'
CUSTOM_MUSIC_PATH = 'audio'
OUTPUT_APK_NAME = f'{NEW_PACKAGE_NAME}.apk'
KEYSTORE_PATH = 'my-release-key.keystore'
KEY_ALIAS = 'my-key-alias'
KEYSTORE_PASS = 'android'
KEY_PASS = 'android'


def run_command(command, step_name):
    print(f'{Fore.CYAN}==> [Running] {step_name}...')

    try:
        result = subprocess.run(command, shell=True, check=True)

        print(f'{Fore.GREEN}✓   [Success] {step_name}')

        return True
    except subprocess.CalledProcessError as e:
        print(f'{Fore.RED}✗   [ERROR] {step_name}')
        print(f'{Fore.RED}    Exit code: {e.returncode}')

        if e.stderr:
            print(f'{Fore.RED}    Error output: {e.stderr.strip()}')

        if e.stdout:
            print(f'{Fore.YELLOW}    Output: {e.stdout.strip()}')

        return False
    except FileNotFoundError as e:
        print(f'{Fore.RED}✗   [ERROR] Command not found: {command.split()[0]}')
        print(f'{Fore.RED}    Make sure apktool, keytool and apksigner are in your system PATH.')

        return False
    except Exception as e:
        print(f'{Fore.RED}✗   [ERROR] Unexpected error: {e}')

        return False


def rename_package_directories(project_dir, old_package, new_package):
    print(f'{Fore.CYAN}==> [Renaming] Package directories...')
    
    old_package_path = old_package.replace('.', os.sep)
    new_package_path = new_package.replace('.', os.sep)
    
    dirs_renamed = 0

    smali_dirs = [d for d in os.listdir(project_dir) if d.startswith('smali')]
    
    for smali_dir_name in smali_dirs:
        smali_dir = os.path.join(project_dir, smali_dir_name)
        
        if not os.path.exists(smali_dir):
            continue
        
        old_full_path = os.path.join(smali_dir, old_package_path)
        
        if os.path.exists(old_full_path):
            new_full_path = os.path.join(smali_dir, new_package_path)
            new_parent_dir = os.path.dirname(new_full_path)
            
            try:
                os.makedirs(new_parent_dir, exist_ok=True)
                
                if os.path.exists(new_full_path):
                    shutil.rmtree(new_full_path)
                
                shutil.move(old_full_path, new_full_path)
                
                print(f'{Fore.GREEN}    ✓ Renamed: {smali_dir_name}/{old_package_path} -> {smali_dir_name}/{new_package_path}')

                dirs_renamed += 1

                try:
                    old_parts = old_package.split('.')

                    for i in range(len(old_parts) - 1, 0, -1):
                        old_parent = os.path.join(smali_dir, *old_parts[:i])

                        if os.path.exists(old_parent) and not os.listdir(old_parent):
                            os.rmdir(old_parent)
                except:
                    pass
            except Exception as e:
                print(f'{Fore.YELLOW}    ! Could not rename {smali_dir_name}/{old_package_path}: {e}')
    
    if dirs_renamed > 0:
        print(f'{Fore.GREEN}✓   [Success] Renamed {dirs_renamed} package directories')

    else:
        print(f'{Fore.YELLOW}WARNING: No package directories found to rename')
    
    return True


def modify_package_name(project_dir, old_package, new_package):
    print(f'{Fore.CYAN}==> [Modifying] Package name: {old_package} -> {new_package}')
    
    files_modified = 0
    
    target_files = [
        'AndroidManifest.xml',
        'apktool.yml',
        'res/values/strings.xml',
        'res/values/public.xml',
    ]
    
    for file_name in target_files:
        file_path = os.path.join(project_dir, file_name)
        
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                if old_package in content:
                    content = content.replace(old_package, new_package)
                    
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(content)
                    
                    print(f'{Fore.GREEN}    ✓ Modified: {file_name}')

                    files_modified += 1
            except Exception as e:
                print(f'{Fore.YELLOW}    ! Could not modify {file_name}: {e}')
    
    res_dir = os.path.join(project_dir, 'res')
    
    if os.path.exists(res_dir):
        for root, dirs, files in os.walk(res_dir):
            for file in files:
                if file.endswith('.xml'):
                    file_path = os.path.join(root, file)
                    
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                        
                        if old_package in content:
                            content = content.replace(old_package, new_package)
                            
                            with open(file_path, 'w', encoding='utf-8') as f:
                                f.write(content)
                            
                            rel_path = os.path.relpath(file_path, project_dir)

                            print(f'{Fore.GREEN}    ✓ Modified: {rel_path}')

                            files_modified += 1
                    except Exception as e:
                        pass

    smali_dirs = [d for d in os.listdir(project_dir) if d.startswith('smali')]
    
    old_package_path = old_package.replace('.', '/')
    new_package_path = new_package.replace('.', '/')
    
    for smali_dir_name in smali_dirs:
        smali_dir = os.path.join(project_dir, smali_dir_name)
        
        if os.path.exists(smali_dir):
            for root, dirs, files in os.walk(smali_dir):
                for file in files:
                    if file.endswith('.smali'):
                        file_path = os.path.join(root, file)
                        
                        try:
                            with open(file_path, 'r', encoding='utf-8') as f:
                                content = f.read()
                            
                            modified = False
                            
                            if old_package in content:
                                content = content.replace(old_package, new_package)
                                modified = True
                            
                            if old_package_path in content:
                                content = content.replace(old_package_path, new_package_path)
                                modified = True
                            
                            if modified:
                                with open(file_path, 'w', encoding='utf-8') as f:
                                    f.write(content)
                                
                                files_modified += 1
                        except Exception as e:
                            pass
    
    if files_modified > 0:
        print(f'{Fore.GREEN}✓   [Success] Package name modified in {files_modified} files')

        return True

    else:
        print(f'{Fore.YELLOW}WARNING: No files were modified. Package name might not exist.')\

        return True


def change_app_name(project_dir, old_name, new_name):
    print(f'{Fore.CYAN}==> [Changing] App name: {old_name} -> {new_name}')
    
    strings_paths = [
        os.path.join(project_dir, 'res', 'values', 'strings.xml'),
        os.path.join(project_dir, 'res', 'values-en', 'strings.xml'),
    ]
    
    files_modified = 0

    res_dir = os.path.join(project_dir, 'res')
    
    if os.path.exists(res_dir):
        for folder in os.listdir(res_dir):
            if folder.startswith('values'):
                strings_path = os.path.join(res_dir, folder, 'strings.xml')

                if strings_path not in strings_paths and os.path.exists(strings_path):
                    strings_paths.append(strings_path)
    
    for strings_path in strings_paths:
        if not os.path.exists(strings_path):
            continue
        
        try:
            with open(strings_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            modified = False
            
            if f'<string name="app_name">{old_name}</string>' in content:
                content = content.replace(
                    f'<string name="app_name">{old_name}</string>',
                    f'<string name="app_name">{new_name}</string>'
                )

                modified = True
            
            if f'<string name="application_name">{old_name}</string>' in content:
                content = content.replace(
                    f'<string name="application_name">{old_name}</string>',
                    f'<string name="application_name">{new_name}</string>'
                )

                modified = True
            
            if old_name in content:
                content = re.sub(
                    f'(<string[^>]*>){old_name}(</string>)',
                    f'\\1{new_name}\\2',
                    content
                )

                modified = True
            
            if modified:
                with open(strings_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                
                rel_path = os.path.relpath(strings_path, project_dir)

                print(f'{Fore.GREEN}    ✓ Modified: {rel_path}')

                files_modified += 1
        except Exception as e:
            print(f'{Fore.YELLOW}    ! Could not modify {strings_path}: {e}')
    
    if files_modified > 0:
        print(f'{Fore.GREEN}✓   [Success] App name changed in {files_modified} files')

    else:
        print(f'{Fore.YELLOW}WARNING: No app name found to change')
    
    return True


def replace_app_icon(project_dir, icon_path):
    if not os.path.exists(icon_path):
        print(f'{Fore.YELLOW}WARNING: Custom icon "{icon_path}" not found. Skipping icon replacement.')

        return True
    
    print(f'{Fore.CYAN}==> [Replacing] App icon with {icon_path}')
    
    res_dir = os.path.join(project_dir, 'res')
    
    if not os.path.exists(res_dir):
        print(f'{Fore.RED}ERROR: res directory not found!{Style.RESET_ALL}')

        return False
    
    icon_replaced = False
    
    for root, dirs, files in os.walk(res_dir):
        folder_name = os.path.basename(root)
        
        if folder_name.startswith('mipmap') or folder_name.startswith('drawable'):
            for file in files:
                if 'ic_launcher' in file and file.endswith('.png'):
                    target_path = os.path.join(root, file)
                    
                    try:
                        shutil.copy2(icon_path, target_path)

                        print(f'{Fore.GREEN}    ✓ Replaced: {target_path}')

                        icon_replaced = True
                    except Exception as e:
                        print(f'{Fore.YELLOW}    ! Could not replace {target_path}: {e}')
    
    if icon_replaced:
        print(f'{Fore.GREEN}✓   [Success] App icon replaced')

    else:
        print(f'{Fore.YELLOW}WARNING: No icon files found to replace')
    
    return True


def change_splash_color(project_dir, new_color):
    print(f'{Fore.CYAN}==> [Modifying] Splash screen XML: Applying black background...')
    
    splash_xml_path = os.path.join(project_dir, 'res', 'drawable', 'splash_screen.xml')
    
    if not os.path.exists(splash_xml_path):
        print(f'{Fore.RED}ERROR: res/drawable/splash_screen.xml not found!{Style.RESET_ALL}')

        return False
        
    try:
        with open(splash_xml_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        modified = False
        
        target_regex = r'\s*<item android:drawable="@color/colorAccent"\s*/>'
        replacement_str = f'    \n<item>\n        <shape android:shape="rectangle">\n            <solid android:color="{new_color}" />\n        </shape>\n    </item>'
        
        new_content = re.sub(target_regex, replacement_str, content)
        
        if new_content != content:
            modified = True
            content = new_content

            print(f'{Fore.GREEN}    ✓ Replaced background layer with solid black')

        else:
            print(f'{Fore.YELLOW}    ! Could not find background layer to replace')

        vivox_regex = r'\s*<item android:bottom[^>]*>[\s\S]*?android:src="@drawable/vivox_logo"[\s\S]*?</item>'
        new_content = re.sub(vivox_regex, '', content, flags=re.DOTALL)
        
        if new_content != content:
            modified = True
            content = new_content

            print(f'{Fore.GREEN}    ✓ Removed vivox_logo item')

        else:
            print(f'{Fore.YELLOW}    ! Could not find vivox_logo item to remove')

        if modified:
            with open(splash_xml_path, 'w', encoding='utf-8') as f:
                f.write(content)

            print(f'{Fore.GREEN}✓   [Success] Modified {os.path.relpath(splash_xml_path, project_dir)}')

        else:
            print(f'{Fore.YELLOW}WARNING: No modifications made to splash_screen.xml')

        return True
    except Exception as e:
        print(f'{Fore.RED}✗   [ERROR] Failed to modify {splash_xml_path}: {e}')

        return False


def replace_music_files(project_dir, source_music_dir):
    print(f'{Fore.CYAN}==> [Replacing] Music files from {source_music_dir}...')
    
    target_dir = os.path.join(project_dir, 'res', 'raw')
    
    if not os.path.exists(source_music_dir):
        print(f'{Fore.YELLOW}WARNING: Source music directory "{source_music_dir}" not found. Skipping music replacement.')
        
        return True
        
    if not os.path.exists(target_dir):
        print(f'{Fore.YELLOW}WARNING: Target directory "{os.path.relpath(target_dir, project_dir)}" not found. Skipping music replacement.')
        
        return True
        
    files_replaced = 0
    
    for file_name in os.listdir(source_music_dir):
        source_file_path = os.path.join(source_music_dir, file_name)
        
        if os.path.isfile(source_file_path):
            target_file_path = os.path.join(target_dir, file_name)
            
            if os.path.exists(target_file_path):
                try:
                    shutil.copy2(source_file_path, target_file_path)
                    
                    print(f'{Fore.GREEN}    ✓ Replaced: {os.path.relpath(target_file_path, project_dir)}')
                    
                    files_replaced += 1
                except Exception as e:
                    print(f'{Fore.RED}    ✗ ERROR replacing {file_name}: {e}')
            
            else:
                print(f'{Fore.YELLOW}    ! Skipping: {file_name} (file not found in {os.path.relpath(target_dir, project_dir)})')
    
    if files_replaced > 0:
        print(f'{Fore.GREEN}✓   [Success] Replaced {files_replaced} music file(s)')

    else:
        print(f'{Fore.YELLOW}WARNING: No matching music files found in target to replace.')
        
    return True


print(f'{Fore.GREEN}======================================================')
print(f'{Fore.GREEN}==               APK Builder & Signer               ==')
print(f'{Fore.GREEN}======================================================')
print(f'Old package:    {PROJECT_DIR}')
print(f'New package:    {NEW_PACKAGE_NAME}')
print(f'Old app name:   {OLD_APP_NAME}')
print(f'New app name:   {NEW_APP_NAME}')
print(f'Custom icon:    {CUSTOM_ICON_PATH}')
print(f'Custom music:   {CUSTOM_MUSIC_PATH}')
print(f'Output file:    {OUTPUT_APK_NAME}')
print(f'Keystore:       {KEYSTORE_PATH}\n')

if not os.path.exists(PROJECT_DIR):
    print(f'{Fore.RED}ERROR: Project directory "{PROJECT_DIR}" not found!{Style.RESET_ALL}')

    sys.exit(1)

if not modify_package_name(PROJECT_DIR, 'com.werewolfapps.online', NEW_PACKAGE_NAME):
    sys.exit(1)

if not rename_package_directories(PROJECT_DIR, 'com.werewolfapps.online', NEW_PACKAGE_NAME):
    sys.exit(1)

if not change_app_name(PROJECT_DIR, OLD_APP_NAME, NEW_APP_NAME):
    sys.exit(1)

if not replace_app_icon(PROJECT_DIR, CUSTOM_ICON_PATH):
    sys.exit(1)

if not change_splash_color(PROJECT_DIR, NEW_SPLASH_COLOR):
    sys.exit(1)

if not replace_music_files(PROJECT_DIR, CUSTOM_MUSIC_PATH):
    sys.exit(1)

cmd_build = f'apktool b {PROJECT_DIR} -f -o {OUTPUT_APK_NAME}'

if not run_command(cmd_build, 'Building APK'):
    sys.exit(1)

if not os.path.exists(OUTPUT_APK_NAME):
    print(f'{Fore.RED}ERROR: APK file was not created!{Style.RESET_ALL}')

    sys.exit(1)

print(f'{Fore.CYAN}==> [Checking] Keystore "{KEYSTORE_PATH}"...')

if not os.path.exists(KEYSTORE_PATH):
    print(f'{Fore.YELLOW}    --- Keystore not found. Creating new one... ---')

    dname = 'CN=Modder, OU=Modding, O=Home, L=City, S=State, C=US'

    cmd_keytool = (
        f'keytool -genkey -v -keystore "{KEYSTORE_PATH}" -alias "{KEY_ALIAS}" '
        f'-storepass {KEYSTORE_PASS} -keypass {KEY_PASS} -dname "{dname}" '
        f'-keyalg RSA -keysize 2048 -validity 10000'
    )

    if not run_command(cmd_keytool, 'Creating Keystore'):
        sys.exit(1)

else:
    print(f'{Fore.GREEN}    --- Keystore found. ---')

cmd_sign = (
    f'apksigner sign --ks "{KEYSTORE_PATH}" '
    f'--ks-key-alias "{KEY_ALIAS}" --ks-pass "pass:{KEYSTORE_PASS}" '
    f'--key-pass "pass:{KEY_PASS}" "{OUTPUT_APK_NAME}"'
)

if not run_command(cmd_sign, 'Signing APK'):
    sys.exit(1)

cmd_verify = f'apksigner verify "{OUTPUT_APK_NAME}"'

if not run_command(cmd_verify, 'Verifying signature'):
    print(f'{Fore.YELLOW}    WARNING: Signature verification failed.')

else:
    print(f'{Fore.GREEN}    APK signature is valid!')

print()
print(f'{Fore.GREEN}======================================================')
print(f'{Fore.GREEN}DONE! File: {OUTPUT_APK_NAME}')
print(f'{Fore.GREEN}======================================================')
print(f'{Fore.CYAN}Next steps:')
print(f'{Fore.CYAN}  1. Install: adb install -r {OUTPUT_APK_NAME}')
print(f'{Fore.CYAN}  2. Run: python run_mod.py')
print(f'{Fore.GREEN}======================================================')
