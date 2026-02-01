import os
import sys
import subprocess
import shutil
import re
import yaml
from pathlib import Path
from colorama import Fore, Style, Back, init

init(autoreset=True)

PROJECT_DIR = 'com.werewolfapps.online'
NEW_PACKAGE_NAME = 'com.mentalist.mobile'
OLD_PACKAGE_NAME = 'com.werewolfapps.online'
OLD_APP_NAME = 'Wolvesville'
NEW_APP_NAME = 'Mentalist'
CUSTOM_ICON_PATH = 'mentalist-mobile.png'
NEW_SPLASH_COLOR = '#000000'
CUSTOM_MUSIC_PATH = 'audio'
KEYSTORE_PATH = 'mentalist.keystore'
KEY_ALIAS = 'mentalist'
KEYSTORE_PASS = 'android'
KEY_PASS = 'android'

FRIDA_GADGET_SO = 'libfrida-gadget.so'
FRIDA_TARGET_ARCH = 'arm64-v8a'


class BuildOrchestrator:
	def __init__(self):
		self.project_dir = Path(PROJECT_DIR)
		self.version_code = 'unknown'
		self.version_name = 'unknown'
	
	def print_header(self, text):
		print(f'\n{Style.BRIGHT}{Back.BLUE}{"=" * 80}{Back.RESET}')
		print(f'{Style.BRIGHT}{Back.BLUE}{text.center(80)}{Back.RESET}')
		print(f'{Style.BRIGHT}{Back.BLUE}{"=" * 80}{Back.RESET}\n')
	
	def print_step(self, text):
		print(f'{Style.BRIGHT}{Fore.CYAN}► {text}{Fore.RESET}')
	
	def print_success(self, text):
		print(f'{Style.BRIGHT}{Fore.GREEN}✓ {text}{Fore.RESET}')
	
	def print_warning(self, text):
		print(f'{Style.BRIGHT}{Fore.YELLOW}⚠ {text}{Fore.RESET}')
	
	def print_error(self, text):
		print(f'{Style.BRIGHT}{Fore.RED}✗ {text}{Fore.RESET}')
	
	def print_info(self, text):
		print(f'{Fore.WHITE}  {text}{Fore.RESET}')
	
	def get_apk_version(self):
		self.print_step('Reading APK version...')
		
		apktool_yml = self.project_dir / 'apktool.yml'
		
		if not apktool_yml.exists():
			self.print_warning('apktool.yml not found')

			return False
		
		try:
			with open(apktool_yml, 'r', encoding='utf-8') as f:
				data = yaml.safe_load(f)
			
			version_info = data.get('versionInfo', {})

			self.version_code = version_info.get('versionCode', 'unknown')
			self.version_name = version_info.get('versionName', 'unknown')
			
			self.print_info(f'Version Code: {self.version_code}')
			self.print_info(f'Version Name: {self.version_name}')
			self.print_success('Version info loaded')
			
			return True
		except Exception as e:
			self.print_error(f'Failed to read version: {e}')

			return False
	
	def run_command(self, command, step_name):
		self.print_step(step_name)
		
		try:
			result = subprocess.run(
				command,
				shell=True,
				check=True,
				# capture_output=True,
				text=True
			)
			
			self.print_success(step_name)

			return True
		except subprocess.CalledProcessError as e:
			self.print_error(f'{step_name} failed')
			self.print_info(f'Exit code: {e.returncode}')
			
			if e.stderr:
				self.print_info(f'Error: {e.stderr.strip()}')
			
			return False
		except FileNotFoundError:
			self.print_error(f'Command not found: {command.split()[0]}')

			return False
		except Exception as e:
			self.print_error(f'Unexpected error: {e}')

			return False
	
	def patch_android_manifest(self):
		self.print_step('Patching AndroidManifest.xml...')
		
		manifest_path = self.project_dir / 'AndroidManifest.xml'
		
		if not manifest_path.exists():
			self.print_error('AndroidManifest.xml not found')

			return False
		
		try:
			with open(manifest_path, 'r', encoding='utf-8') as f:
				content = f.read()

			if 'android.permission.SYSTEM_ALERT_WINDOW' in content:
				self.print_info('SYSTEM_ALERT_WINDOW permission already exists')
				self.print_success('Manifest already patched')

				return True
			
			permission_line = '    <uses-permission android:name="android.permission.SYSTEM_ALERT_WINDOW"/>\n'

			if '<queries>' in content:
				content = content.replace('<queries>', permission_line + '    <queries>', 1)
				
				self.print_info('Inserted SYSTEM_ALERT_WINDOW permission before <queries>')

			elif '<permission' in content:
				content = content.replace('<permission', permission_line + '    <permission', 1)
				
				self.print_info('Inserted SYSTEM_ALERT_WINDOW permission before <permission>')

			elif '<application' in content:
				content = content.replace('<application', permission_line + '    <application', 1)
				
				self.print_info('Inserted SYSTEM_ALERT_WINDOW permission before <application>')
			
			else:
				self.print_error('Could not find insertion point in manifest')

				return False
			
			with open(manifest_path, 'w', encoding='utf-8') as f:
				f.write(content)
			
			self.print_success('AndroidManifest.xml patched')

			return True
		except Exception as e:
			self.print_error(f'Failed to patch manifest: {e}')

			return False
	
	def copy_frida_gadget(self):
		self.print_step('Copying Frida Gadget library...')

		if not Path(FRIDA_GADGET_SO).exists():
			self.print_error(f'{FRIDA_GADGET_SO} not found in current directory')

			return False

		target_dir = self.project_dir / 'lib' / FRIDA_TARGET_ARCH

		target_dir.mkdir(parents=True, exist_ok=True)

		target_file = target_dir / FRIDA_GADGET_SO
		
		try:
			if target_file.exists():
				self.print_info(f'{FRIDA_GADGET_SO} already exists in {target_dir.relative_to(self.project_dir)}')

				source_size = Path(FRIDA_GADGET_SO).stat().st_size
				target_size = target_file.stat().st_size
				
				if source_size == target_size:
					self.print_success('Frida Gadget already up to date')

					return True

				else:
					self.print_info('File size differs, updating...')
  
			shutil.copy2(FRIDA_GADGET_SO, target_file)
			
			file_size_mb = target_file.stat().st_size / (1024 * 1024)

			self.print_info(f'Copied to: {target_file.relative_to(self.project_dir)}')
			self.print_info(f'Size: {file_size_mb:.2f} MB')
			self.print_success('Frida Gadget copied successfully')
			
			return True
		except Exception as e:
			self.print_error(f'Failed to copy Frida Gadget: {e}')

			return False
	
	def find_main_activity_smali(self):
		possible_paths = []

		for smali_dir in self.project_dir.glob('smali*'):
			if not smali_dir.is_dir():
				continue

			new_path = smali_dir / NEW_PACKAGE_NAME.replace('.', '/') / 'MainActivity.smali'
		   
			if new_path.exists():
				possible_paths.append(new_path)

			old_path = smali_dir / OLD_PACKAGE_NAME.replace('.', '/') / 'MainActivity.smali'
			
			if old_path.exists():
				possible_paths.append(old_path)
		
		if not possible_paths:
			return None

		return possible_paths[0]
	
	def patch_main_activity_smali(self):
		self.print_step('Patching MainActivity.smali...')

		smali_path = self.find_main_activity_smali()
		
		if not smali_path:
			self.print_error('MainActivity.smali not found')

			return False
		
		self.print_info(f'Found: {smali_path.relative_to(self.project_dir)}')
		
		try:
			with open(smali_path, 'r', encoding='utf-8') as f:
				content = f.read()

			if 'frida-gadget' in content and 'loadLibrary' in content:
				self.print_info('MainActivity already patched with Frida')
				self.print_success('Smali already patched')

				return True

			onCreate_pattern = r'\.method protected onCreate\(Landroid/os/Bundle;\)V'
			onCreate_match = re.search(onCreate_pattern, content)
			
			if not onCreate_match:
				self.print_error('onCreate method not found in MainActivity.smali')

				return False
			
			onCreate_start = onCreate_match.start()
			
			locals_pattern = r'\.locals (\d+)'
			locals_match = re.search(locals_pattern, content[onCreate_start:])
			
			if not locals_match:
				self.print_error('.locals directive not found in onCreate')

				return False

			current_locals = int(locals_match.group(1))
			new_locals = max(current_locals, 3)

			locals_pos = onCreate_start + locals_match.start()
			locals_end = onCreate_start + locals_match.end()
			
			new_locals_line = f'.locals {new_locals}'
			content = content[:locals_pos] + new_locals_line + content[locals_end:]

			invoke_super_pattern = r'invoke-super \{[^}]+\}, Lcom/facebook/react/ReactActivity;->onCreate\(Landroid/os/Bundle;\)V'
			invoke_super_match = re.search(invoke_super_pattern, content[onCreate_start:])
			
			if not invoke_super_match:
				self.print_error('invoke-super call not found in onCreate')

				return False

			insert_pos = onCreate_start + invoke_super_match.end()

			frida_code = '''

	.line 47
	const-string v2, "frida-gadget"
	invoke-static {v2}, Ljava/lang/System;->loadLibrary(Ljava/lang/String;)V
'''

			content = content[:insert_pos] + frida_code + content[insert_pos:]

			with open(smali_path, 'w', encoding='utf-8') as f:
				f.write(content)
			
			self.print_info(f'Updated .locals from {current_locals} to {new_locals}')
			self.print_info('Injected Frida Gadget loading code')
			self.print_success('MainActivity.smali patched successfully')
			
			return True
			
		except Exception as e:
			self.print_error(f'Failed to patch MainActivity.smali: {e}')

			import traceback

			traceback.print_exc()

			return False
	
	def rename_package_directories(self):
		self.print_step('Renaming package directories...')
		
		old_package_path = OLD_PACKAGE_NAME.replace('.', os.sep)
		new_package_path = NEW_PACKAGE_NAME.replace('.', os.sep)
		
		dirs_renamed = 0
		
		smali_dirs = [d for d in self.project_dir.iterdir() if d.name.startswith('smali') and d.is_dir()]
		
		for smali_dir in smali_dirs:
			old_full_path = smali_dir / old_package_path
			
			if old_full_path.exists():
				new_full_path = smali_dir / new_package_path
				new_parent_dir = new_full_path.parent
				
				try:
					new_parent_dir.mkdir(parents=True, exist_ok=True)
					
					if new_full_path.exists():
						shutil.rmtree(new_full_path)
					
					shutil.move(str(old_full_path), str(new_full_path))
					
					self.print_info(f'Renamed: {smali_dir.name}/{old_package_path} → {new_package_path}')
					
					dirs_renamed += 1

					try:
						old_parts = OLD_PACKAGE_NAME.split('.')
						
						for i in range(len(old_parts) - 1, 0, -1):
							old_parent = smali_dir.joinpath(*old_parts[:i])
							
							if old_parent.exists() and not any(old_parent.iterdir()):
								old_parent.rmdir()
					except:
						pass
				except Exception as e:
					self.print_warning(f'Could not rename {smali_dir.name}/{old_package_path}: {e}')
		
		if dirs_renamed > 0:
			self.print_success(f'Renamed {dirs_renamed} package directories')

		else:
			self.print_warning('No package directories found to rename')
		
		return True
	
	def modify_package_name(self):
		self.print_step(f'Modifying package name: {OLD_PACKAGE_NAME} → {NEW_PACKAGE_NAME}')
		
		files_modified = 0
		
		target_files = [
			'AndroidManifest.xml',
			'apktool.yml',
			'res/values/strings.xml',
			'res/values/public.xml'
		]
		
		for file_name in target_files:
			file_path = self.project_dir / file_name
			
			if file_path.exists():
				try:
					with open(file_path, 'r', encoding='utf-8') as f:
						content = f.read()
					
					if OLD_PACKAGE_NAME in content:
						content = content.replace(OLD_PACKAGE_NAME, NEW_PACKAGE_NAME)
						
						with open(file_path, 'w', encoding='utf-8') as f:
							f.write(content)
						
						self.print_info(f'Modified: {file_name}')

						files_modified += 1
				except Exception as e:
					self.print_warning(f'Could not modify {file_name}: {e}')

		res_dir = self.project_dir / 'res'

		if res_dir.exists():
			for xml_file in res_dir.rglob('*.xml'):
				try:
					with open(xml_file, 'r', encoding='utf-8') as f:
						content = f.read()
					
					if OLD_PACKAGE_NAME in content:
						content = content.replace(OLD_PACKAGE_NAME, NEW_PACKAGE_NAME)
						
						with open(xml_file, 'w', encoding='utf-8') as f:
							f.write(content)
						
						files_modified += 1
				except:
					pass

		old_package_path = OLD_PACKAGE_NAME.replace('.', '/')
		new_package_path = NEW_PACKAGE_NAME.replace('.', '/')
		
		for smali_dir in [d for d in self.project_dir.iterdir() if d.name.startswith('smali')]:
			if smali_dir.is_dir():
				for smali_file in smali_dir.rglob('*.smali'):
					try:
						with open(smali_file, 'r', encoding='utf-8') as f:
							content = f.read()
						
						modified = False
						
						if OLD_PACKAGE_NAME in content:
							content = content.replace(OLD_PACKAGE_NAME, NEW_PACKAGE_NAME)
							modified = True
						
						if old_package_path in content:
							content = content.replace(old_package_path, new_package_path)
							modified = True
						
						if modified:
							with open(smali_file, 'w', encoding='utf-8') as f:
								f.write(content)

							files_modified += 1
					except:
						pass
		
		self.print_success(f'Modified {files_modified} files')

		return True
	
	def change_app_name(self):
		self.print_step(f'Changing app name: {OLD_APP_NAME} → {NEW_APP_NAME}')
		
		strings_xml = self.project_dir / 'res' / 'values' / 'strings.xml'
		
		if not strings_xml.exists():
			self.print_warning('strings.xml not found')

			return True
		
		try:
			with open(strings_xml, 'r', encoding='utf-8') as f:
				content = f.read()
			
			pattern = r'<string name="app_name">[^<]+</string>'
			replacement = f'<string name="app_name">{NEW_APP_NAME}</string>'
			
			new_content = re.sub(pattern, replacement, content)
			
			if new_content != content:
				with open(strings_xml, 'w', encoding='utf-8') as f:
					f.write(new_content)
				
				self.print_success('App name changed')\

			else:
				self.print_warning('App name pattern not found')
			
			return True
		except Exception as e:
			self.print_error(f'Failed to change app name: {e}')

			return False
	
	def replace_app_icon(self):
		self.print_step(f'Replacing app icon with {CUSTOM_ICON_PATH}...')
		
		if not Path(CUSTOM_ICON_PATH).exists():
			self.print_warning(f'{CUSTOM_ICON_PATH} not found, skipping')

			return True
		
		icons_replaced = 0
		mipmap_dirs = list(self.project_dir.glob('res/mipmap-*'))
		
		for mipmap_dir in mipmap_dirs:
			if 'anydpi' in mipmap_dir.name:
				self.print_info(f'Skipping adaptive icon directory: {mipmap_dir.name}')
				
				continue
			
			target_files = list(mipmap_dir.glob('ic_launcher.*'))
			
			for target_file in target_files:
				if target_file.suffix.lower() == '.xml':
					self.print_info(f'Skipping XML adaptive icon: {target_file.relative_to(self.project_dir)}')
					
					continue
				
				try:
					shutil.copy2(CUSTOM_ICON_PATH, target_file)
					
					self.print_info(f'Replaced: {target_file.relative_to(self.project_dir)}')
					
					icons_replaced += 1
				except Exception as e:
					self.print_warning(f'Could not replace {target_file.name}: {e}')
		
		if icons_replaced > 0:
			self.print_success(f'Replaced {icons_replaced} icon files')
		
		else:
			self.print_warning('No icon files found to replace')
		
		return True

	def change_splash_color(self):
		self.print_step('Modifying splash screen...')
		
		splash_xml = self.project_dir / 'res' / 'drawable' / 'splash_screen.xml'
		
		if not splash_xml.exists():
			self.print_warning('splash_screen.xml not found, skipping')

			return True
		
		try:
			with open(splash_xml, 'r', encoding='utf-8') as f:
				content = f.read()
			
			modified = False

			target_regex = r'\s*<item android:drawable="@color/colorAccent"\s*/>'
			replacement_str = f'    \n<item>\n        <shape android:shape="rectangle">\n            <solid android:color="{NEW_SPLASH_COLOR}" />\n        </shape>\n    </item>'
			
			new_content = re.sub(target_regex, replacement_str, content)
			
			if new_content != content:
				modified = True
				content = new_content

				self.print_info('Replaced background with black')

			vivox_regex = r'\s*<item android:bottom[^>]*>[\s\S]*?android:src="@drawable/vivox_logo"[\s\S]*?</item>'
			new_content = re.sub(vivox_regex, '', content, flags=re.DOTALL)
			
			if new_content != content:
				modified = True
				content = new_content

				self.print_info('Removed vivox_logo')
			
			if modified:
				with open(splash_xml, 'w', encoding='utf-8') as f:
					f.write(content)
				
				self.print_success('Splash screen modified')

			else:
				self.print_warning('No modifications made')
			
			return True
		except Exception as e:
			self.print_error(f'Failed to modify splash: {e}')

			return False
	
	def replace_music_files(self):
		self.print_step(f'Replacing music files from {CUSTOM_MUSIC_PATH}...')
		
		if not Path(CUSTOM_MUSIC_PATH).exists():
			self.print_warning(f'{CUSTOM_MUSIC_PATH} not found, skipping')

			return True
		
		target_dir = self.project_dir / 'res' / 'raw'
		
		if not target_dir.exists():
			self.print_warning('res/raw not found, skipping')

			return True
		
		files_replaced = 0
		
		for source_file in Path(CUSTOM_MUSIC_PATH).iterdir():
			if source_file.is_file():
				target_file = target_dir / source_file.name
				
				if target_file.exists():
					try:
						shutil.copy2(source_file, target_file)
						
						self.print_info(f'Replaced: {target_file.relative_to(self.project_dir)}')
						
						files_replaced += 1
					except Exception as e:
						self.print_warning(f'Could not replace {source_file.name}: {e}')
		
		if files_replaced > 0:
			self.print_success(f'Replaced {files_replaced} music files')

		else:
			self.print_warning('No matching music files found')
		
		return True
	
	def create_keystore(self):
		self.print_step(f'Checking keystore {KEYSTORE_PATH}...')
		
		if Path(KEYSTORE_PATH).exists():
			self.print_info('Keystore found')
			self.print_success('Keystore ready')

			return True
		
		self.print_info('Keystore not found, creating...')
		
		dname = 'CN=Modder, OU=Modding, O=Home, L=City, S=State, C=US'
		
		cmd = (
			f'keytool -genkey -v -keystore "{KEYSTORE_PATH}" -alias "{KEY_ALIAS}" '
			f'-storepass {KEYSTORE_PASS} -keypass {KEY_PASS} -dname "{dname}" '
			f'-keyalg RSA -keysize 2048 -validity 10000'
		)
		
		return self.run_command(cmd, 'Creating keystore')
	
	def build_apk(self, output_name):
		cmd = f'apktool b {PROJECT_DIR} -f -o {output_name}'

		return self.run_command(cmd, 'Building APK')
	
	def sign_apk(self, apk_name):
		cmd = (
			f'apksigner sign --ks "{KEYSTORE_PATH}" '
			f'--ks-key-alias "{KEY_ALIAS}" --ks-pass "pass:{KEYSTORE_PASS}" '
			f'--key-pass "pass:{KEY_PASS}" "{apk_name}"'
		)

		return self.run_command(cmd, 'Signing APK')
	
	def verify_apk(self, apk_name):
		cmd = f'apksigner verify "{apk_name}"'

		return self.run_command(cmd, 'Verifying APK signature')
	
	def print_build_summary(self, output_apk):
		self.print_header('BUILD SUMMARY')
		
		print(f'{Fore.CYAN}Project:{Fore.RESET} {Style.BRIGHT}{PROJECT_DIR}{Style.RESET_ALL}')
		print(f'{Fore.CYAN}Old Package:{Fore.RESET} {OLD_PACKAGE_NAME}')
		print(f'{Fore.CYAN}New Package:{Fore.RESET} {NEW_PACKAGE_NAME}')
		print(f'{Fore.CYAN}Version:{Fore.RESET} {self.version_name} (code: {self.version_code})')
		print(f'{Fore.CYAN}Output:{Fore.RESET} {Style.BRIGHT}{output_apk}{Style.RESET_ALL}')
		
		if Path(output_apk).exists():
			size_mb = Path(output_apk).stat().st_size / (1024 * 1024)

			print(f'{Fore.CYAN}Size:{Fore.RESET} {size_mb:.2f} MB')
		
		print(f'\n{Style.BRIGHT}{Fore.GREEN}Protection Layers:{Fore.RESET}')
		print(f'  • Frida Gadget Integrated')
		print(f'  • SYSTEM_ALERT_WINDOW Permission')
		print(f'  • Package Name Changed')
		print(f'  • Custom Branding Applied')
		
		print(f'\n{Fore.YELLOW}Next Steps:{Fore.RESET}')
		print(f'  1. adb install -r {output_apk}')
		print(f'  2. Run python run_mod.py')
		print(f'  3. Launch app on device')
	
	def execute_build_pipeline(self):
		self.print_header(f'MENTALIST APK BUILDER v1.0')
		
		if not self.project_dir.exists():
			self.print_error(f'Project directory "{PROJECT_DIR}" not found!')

			return False
		
		pipeline_steps = [
			('Read APK Version', self.get_apk_version),
			('Patch AndroidManifest', self.patch_android_manifest),
			('Copy Frida Gadget', self.copy_frida_gadget),
			('Patch MainActivity', self.patch_main_activity_smali),
			('Modify Package Name', self.modify_package_name),
			('Rename Directories', self.rename_package_directories),
			('Change App Name', self.change_app_name),
			('Replace Icon', self.replace_app_icon),
			('Change Splash', self.change_splash_color),
			('Replace Music', self.replace_music_files),
			('Create Keystore', self.create_keystore),
		]
		
		total_steps = len(pipeline_steps)
		completed_steps = 0
		
		for step_num, (step_name, step_func) in enumerate(pipeline_steps, 1):
			print(f'\n{Style.BRIGHT}{Fore.MAGENTA}[Step {step_num}/{total_steps}] {step_name}{Fore.RESET}')
			
			try:
				result = step_func()
				
				if result:
					completed_steps += 1
				else:
					if step_name in ['Replace Icon', 'Change Splash', 'Replace Music']:

						self.print_warning(f'{step_name} skipped or failed, continuing...')
						
						completed_steps += 1

					else:
						self.print_error(f'{step_name} failed')

						return False
			except Exception as e:
				self.print_error(f'{step_name} crashed: {str(e)}')

				import traceback

				traceback.print_exc()

				return False

		if self.version_name != 'unknown':
			output_apk = f'{NEW_PACKAGE_NAME}-v{self.version_name}.apk'

		else:
			output_apk = f'{NEW_PACKAGE_NAME}.apk'

		print(f'\n{Style.BRIGHT}{Fore.MAGENTA}[Step {total_steps + 1}/{total_steps + 3}] Build APK{Fore.RESET}')
		
		if not self.build_apk(output_apk):
			return False
		
		if not Path(output_apk).exists():
			self.print_error('APK file was not created!')

			return False

		print(f'\n{Style.BRIGHT}{Fore.MAGENTA}[Step {total_steps + 2}/{total_steps + 3}] Sign APK{Fore.RESET}')
		
		if not self.sign_apk(output_apk):
			return False

		print(f'\n{Style.BRIGHT}{Fore.MAGENTA}[Step {total_steps + 3}/{total_steps + 3}] Verify Signature{Fore.RESET}')
		
		self.verify_apk(output_apk)
		self.print_build_summary(output_apk)
		
		print(f'\n{Style.BRIGHT}{Back.GREEN}{"═" * 80}{Back.RESET}')
		print(f'{Style.BRIGHT}{Back.GREEN}{"BUILD COMPLETED SUCCESSFULLY".center(80)}{Back.RESET}')
		print(f'{Style.BRIGHT}{Back.GREEN}{"═" * 80}{Back.RESET}\n')
		
		return True


def main():
	orchestrator = BuildOrchestrator()
	
	try:
		success = orchestrator.execute_build_pipeline()

		sys.exit(0 if success else 1)
	except KeyboardInterrupt:
		print(f'\n\n{Fore.YELLOW}Build interrupted by user{Fore.RESET}')

		sys.exit(1)
	except Exception as e:
		print(f'\n{Style.BRIGHT}{Fore.RED}Critical error: {str(e)}{Fore.RESET}')

		import traceback

		traceback.print_exc()
		sys.exit(1)


if __name__ == '__main__':
	main()
