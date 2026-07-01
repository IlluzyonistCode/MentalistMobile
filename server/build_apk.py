import subprocess
import shutil
import yaml
import os
import sys
import re
from pathlib import Path
from colorama import Fore, Style, Back, init

init(autoreset=True)

PROJECT_DIR       = 'com.werewolfapps.online'
NEW_PACKAGE_NAME  = 'com.mentalist.mobile'
OLD_PACKAGE_NAME  = 'com.werewolfapps.online'
OLD_APP_NAME      = 'Wolvesville'
NEW_APP_NAME      = 'Mentalist'
CUSTOM_ICON_PATH  = 'assets/mentalist-mobile.png'
CUSTOM_LOGO_PATH  = 'assets/mentalist-logo.png'
NEW_SPLASH_COLOR  = '#000000'
CUSTOM_MUSIC_PATH = 'audio'
KEYSTORE_PATH     = 'assets/mentalist.keystore'
KEY_ALIAS         = 'mentalist'
KEYSTORE_PASS     = 'android'
KEY_PASS          = 'android'
FRIDA_GADGET_SO   = 'assets/libfrida-gadget.so'
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

	def get_apk_version_from_file(self, apk_path):
		try:
			result = subprocess.run(
				f'aapt dump badging "{apk_path}"',
				shell=True, check=True, text=True,
				capture_output=True
			)

			# На Windows aapt может писать в stderr вместо stdout
			output = result.stdout or result.stderr

			vc_match = re.search(r"versionCode='(\d+)'", output)
			vn_match = re.search(r"versionName='([^']+)'", output)

			return (
				vc_match.group(1) if vc_match else None,
				vn_match.group(1) if vn_match else None,
			)
		except Exception:
			return None, None

	def find_and_decompile_apk(self):
		self.print_step(f'Searching for APK files starting with "{OLD_PACKAGE_NAME}"...')

		candidates = sorted(
			[f for f in Path('assets').glob(f'{OLD_PACKAGE_NAME}*.apk') if f.is_file()] +
			[f for f in Path('.').glob(f'{OLD_PACKAGE_NAME}*.apk') if f.is_file()],
			key=lambda p: p.name,
			reverse=True
		)

		if not candidates:
			self.print_error(
				f'No APK files starting with "{OLD_PACKAGE_NAME}" found in the current directory.'
			)

			return False

		chosen = candidates[0]

		if len(candidates) > 1:
			self.print_info('Multiple matching APK files found:')

			for c in candidates:
				marker = ' ← selected (lexicographically largest)' if c == chosen else ''

				self.print_info(f'  {c.name}{marker}')

		else:
			self.print_info(f'Found: {chosen.name}')

		self.print_info(f'Selected APK: {Style.BRIGHT}{chosen.name}{Style.RESET_ALL}')

		apktool_yml = self.project_dir / 'apktool.yml'

		if self.project_dir.exists() and apktool_yml.exists():
			self.print_step('Existing decompiled directory found — checking version match...')

			try:
				with open(apktool_yml, 'r', encoding='utf-8') as f:
					data = yaml.safe_load(f)

				existing_vc = str(data.get('versionInfo', {}).get('versionCode', ''))
				existing_vn = str(data.get('versionInfo', {}).get('versionName', ''))

				apk_vc, apk_vn = self.get_apk_version_from_file(chosen)

				self.print_info(f'Existing : versionCode={existing_vc}, versionName={existing_vn}')
				self.print_info(f'APK file : versionCode={apk_vc},      versionName={apk_vn}')

				if apk_vc and apk_vn and existing_vc == apk_vc and existing_vn == apk_vn:
					self.print_success(
						f'Version match ({apk_vn}, code {apk_vc}) — '
						f'reusing existing "{PROJECT_DIR}/" directory, skipping decompilation.'
					)

					return True

				else:
					self.print_warning('Version mismatch — removing old directory and redecompiling...')

			except Exception as e:
				self.print_warning(f'Could not read existing apktool.yml: {e} — will redecompile.')

		if self.project_dir.exists():
			self.print_info(
				f'Output directory "{PROJECT_DIR}" already exists — removing before decompilation...'
			)

			try:
				shutil.rmtree(self.project_dir)
			except Exception as e:
				self.print_error(f'Could not remove existing directory: {e}')

				return False

		self.print_step(f'Decompiling: apktool d -f -o {PROJECT_DIR} {chosen.name}')

		try:
			subprocess.run(
				f'apktool d -f -o "{PROJECT_DIR}" "{chosen}"',
				shell=True, check=True, text=True
			)

			self.print_success(f'Decompiled "{chosen.name}" → "{PROJECT_DIR}/"')

			return True
		except subprocess.CalledProcessError as e:
			self.print_error(f'apktool failed (exit code {e.returncode})')

			return False
		except FileNotFoundError:
			self.print_error('apktool not found — make sure it is installed and on PATH')

			return False
		except Exception as e:
			self.print_error(f'Unexpected error during decompilation: {e}')

			return False

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
			subprocess.run(command, shell=True, check=True, text=True)

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

			modified = False

			# ── Точка вставки permissions ────────────────────────────────
			def insert_permission(perm_line, content):
				if perm_line.strip() in content:
					return content, False
				if '<queries>' in content:
					return content.replace('<queries>', perm_line + '    <queries>', 1), True
				elif '<permission' in content:
					return content.replace('<permission', perm_line + '    <permission', 1), True
				elif '<application' in content:
					return content.replace('<application', perm_line + '    <application', 1), True
				return content, False

			# SYSTEM_ALERT_WINDOW
			line_saw = '    <uses-permission android:name="android.permission.SYSTEM_ALERT_WINDOW"/>\n'
			content, added = insert_permission(line_saw, content)
			if added:
				self.print_info('Inserted SYSTEM_ALERT_WINDOW permission')
				modified = True
			else:
				self.print_info('SYSTEM_ALERT_WINDOW already present')

			# BIND_ACCESSIBILITY_SERVICE
			line_bas = '    <uses-permission android:name="android.permission.BIND_ACCESSIBILITY_SERVICE"/>\n'
			content, added = insert_permission(line_bas, content)
			if added:
				self.print_info('Inserted BIND_ACCESSIBILITY_SERVICE permission')
				modified = True
			else:
				self.print_info('BIND_ACCESSIBILITY_SERVICE already present')

			# ── AccessibilityService declaration ─────────────────────────
			if 'MentalistAccessibilityService' not in content:
				accessibility_service = (
					'\n'
					'        <service\n'
					'            android:name="com.mentalist.mobile.MentalistAccessibilityService"\n'
					'            android:exported="true"\n'
					'            android:label="Mentalist"\n'
					'            android:permission="android.permission.BIND_ACCESSIBILITY_SERVICE">\n'
					'            <intent-filter>\n'
					'                <action android:name="android.accessibilityservice.AccessibilityService"/>\n'
					'            </intent-filter>\n'
					'            <meta-data\n'
					'                android:name="android.accessibilityservice"\n'
					'                android:resource="@xml/mentalist_accessibility_config"/>\n'
					'        </service>\n'
				)
				if '</application>' in content:
					content  = content.replace('</application>', accessibility_service + '    </application>', 1)
					modified = True
					self.print_info('Inserted AccessibilityService declaration')
				else:
					self.print_warning('</application> not found — AccessibilityService not added')
			else:
				self.print_info('AccessibilityService already declared')

			if modified:
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
		target_file = target_dir / Path(FRIDA_GADGET_SO).name

		try:
			if target_file.exists():
				self.print_info(
					f'{FRIDA_GADGET_SO} already exists in {target_dir.relative_to(self.project_dir)}'
				)

				if Path(FRIDA_GADGET_SO).stat().st_size == target_file.stat().st_size:
					self.print_success('Frida Gadget already up to date')

					return True

				self.print_info('File size differs, updating...')

			shutil.copy2(FRIDA_GADGET_SO, target_file)

			self.print_info(f'Copied to: {target_file.relative_to(self.project_dir)}')
			self.print_info(f'Size: {target_file.stat().st_size / (1024 * 1024):.2f} MB')
			self.print_success('Frida Gadget copied successfully')

			return True
		except Exception as e:
			self.print_error(f'Failed to copy Frida Gadget: {e}')

			return False

	def _patch_agent_constants(self, server_url: str) -> bool:
		"""
		В production режиме патчит js/constants.js:
		- MENTALIST_MODE = 'production'
		- MENTALIST_SERVER_WS = 'ws://host:port/device'
		- MENTALIST_SERVER_HTTP = 'http://host:port'

		После этого нужно пересобрать agent.js через node build.js.
		"""
		self.print_step('Patching agent constants for production...')

		constants_path = Path(__file__).parent.parent / 'js' / 'constants.js'
		if not constants_path.exists():
			# Пробуем относительный путь
			constants_path = Path('js') / 'constants.js'

		if not constants_path.exists():
			self.print_warning('constants.js not found, skipping agent patch')
			return True

		try:
			content = constants_path.read_text(encoding='utf-8')

			ws_url   = server_url.replace('http://', 'ws://').replace('https://', 'wss://') + '/device'
			http_url = server_url

			import re
			content = re.sub(
				r"export const MENTALIST_MODE\s*=\s*['\"].*?['\"];",
				f"export const MENTALIST_MODE = 'production';",
				content
			)
			content = re.sub(
				r"export const MENTALIST_SERVER_WS\s*=\s*['\"].*?['\"];",
				f"export const MENTALIST_SERVER_WS = '{ws_url}';",
				content
			)
			content = re.sub(
				r"export const MENTALIST_SERVER_HTTP\s*=\s*['\"].*?['\"];",
				f"export const MENTALIST_SERVER_HTTP = '{http_url}';",
				content
			)

			constants_path.write_text(content, encoding='utf-8')
			self.print_success(f'constants.js patched: mode=production, ws={ws_url}')

			# Пересобираем agent.js
			js_dir = constants_path.parent
			build_js = js_dir / 'build.js'
			if build_js.exists():
				self.print_step('Rebuilding agent.js...')
				result = subprocess.run(
					['node', str(build_js)],
					capture_output=True, text=True, cwd=str(js_dir)
				)
				if result.returncode == 0:
					self.print_success('agent.js rebuilt successfully')
				else:
					self.print_warning(f'agent.js rebuild failed: {result.stderr[:200]}')
			else:
				self.print_warning('build.js not found, rebuild agent.js manually')

			return True
		except Exception as e:
			self.print_error(f'_patch_agent_constants failed: {e}')
			return False

	def create_frida_gadget_config(self, server_url: str, server_http: str):
		"""
		Создаёт libfrida-gadget.config.so рядом с libfrida-gadget.so.

		Production режим: Gadget при старте скачивает agent.js с сервера
		и выполняет его — никакого ADB, никакого локального Python.

		server_url  — HTTP URL для скачивания agent.js
		             (например http://1.2.3.4:8765/agent)
		"""
		self.print_step(f'Creating Frida Gadget config (production mode)...')
		self.print_info(f'Agent URL: {server_url}')

		import json

		config = {
			"interaction": {
				"type": "script",
				"parameters": {
					"url": server_url,
					# При обновлении сервера Gadget перезагружает скрипт
					"resumption": "auto"
				}
			}
		}

		target_dir = self.project_dir / 'lib' / FRIDA_TARGET_ARCH
		config_path = target_dir / 'libfrida-gadget.config.so'

		try:
			config_path.write_text(json.dumps(config, indent=2), encoding='utf-8')
			self.print_success(f'Gadget config written: {config_path.relative_to(self.project_dir)}')
			return True
		except Exception as e:
			self.print_error(f'Failed to write Gadget config: {e}')
			return False

	def find_main_activity_smali(self):
		possible_paths = []

		for smali_dir in self.project_dir.glob('smali*'):
			if not smali_dir.is_dir():
				continue

			for pkg in (NEW_PACKAGE_NAME, OLD_PACKAGE_NAME):
				p = smali_dir / pkg.replace('.', '/') / 'MainActivity.smali'

				if p.exists():
					possible_paths.append(p)

		return possible_paths[0] if possible_paths else None

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

			onCreate_match = re.search(
				r'\.method protected onCreate\(Landroid/os/Bundle;\)V', content
			)
			if not onCreate_match:
				self.print_error('onCreate method not found in MainActivity.smali')

				return False

			onCreate_start = onCreate_match.start()

			locals_match = re.search(r'\.locals (\d+)', content[onCreate_start:])

			if not locals_match:
				self.print_error('.locals directive not found in onCreate')

				return False

			current_locals = int(locals_match.group(1))
			new_locals = max(current_locals, 3)
			locals_pos = onCreate_start + locals_match.start()
			locals_end = onCreate_start + locals_match.end()
			content = content[:locals_pos] + f'.locals {new_locals}' + content[locals_end:]

			invoke_super_match = re.search(
				r'invoke-super \{[^}]+\}, Lcom/facebook/react/ReactActivity;->onCreate\(Landroid/os/Bundle;\)V',
				content[onCreate_start:]
			)

			if not invoke_super_match:
				self.print_error('invoke-super call not found in onCreate')

				return False

			insert_pos = onCreate_start + invoke_super_match.end()
			frida_code = (
				'\n\t.line 47'
				'\n\tconst-string v2, "frida-gadget"'
				'\n\tinvoke-static {v2}, Ljava/lang/System;->loadLibrary(Ljava/lang/String;)V'
			)
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

	def modify_package_name(self):
		self.print_step(f'Modifying package name: {OLD_PACKAGE_NAME} → {NEW_PACKAGE_NAME}')

		files_modified = 0
		old_pkg_slash = OLD_PACKAGE_NAME.replace('.', '/')
		new_pkg_slash = NEW_PACKAGE_NAME.replace('.', '/')

		for file_name in ('AndroidManifest.xml', 'apktool.yml',
		                  'res/values/strings.xml', 'res/values/public.xml'):
			file_path = self.project_dir / file_name

			if not file_path.exists():
				continue

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

		for smali_dir in self.project_dir.iterdir():
			if not (smali_dir.name.startswith('smali') and smali_dir.is_dir()):
				continue

			for smali_file in smali_dir.rglob('*.smali'):
				try:
					with open(smali_file, 'r', encoding='utf-8') as f:
						content = f.read()

					modified = False

					if OLD_PACKAGE_NAME in content:
						content = content.replace(OLD_PACKAGE_NAME, NEW_PACKAGE_NAME)
						modified = True

					if old_pkg_slash in content:
						content = content.replace(old_pkg_slash, new_pkg_slash)
						modified = True

					if modified:
						with open(smali_file, 'w', encoding='utf-8') as f:
							f.write(content)

						files_modified += 1
				except:
					pass

		self.print_success(f'Modified {files_modified} files')

		return True

	def rename_package_directories(self):
		self.print_step('Renaming package directories...')

		old_package_path = OLD_PACKAGE_NAME.replace('.', os.sep)
		new_package_path = NEW_PACKAGE_NAME.replace('.', os.sep)
		dirs_renamed = 0

		for smali_dir in [d for d in self.project_dir.iterdir()
		                  if d.name.startswith('smali') and d.is_dir()]:
			old_full_path = smali_dir / old_package_path

			if not old_full_path.exists():
				continue

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

	def change_app_name(self):
		self.print_step(f'Changing app name: {OLD_APP_NAME} → {NEW_APP_NAME}')

		strings_xml = self.project_dir / 'res' / 'values' / 'strings.xml'

		if not strings_xml.exists():
			self.print_warning('strings.xml not found')

			return True

		try:
			with open(strings_xml, 'r', encoding='utf-8') as f:
				content = f.read()

			new_content = re.sub(
				r'<string name="app_name">[^<]+</string>',
				f'<string name="app_name">{NEW_APP_NAME}</string>',
				content
			)

			if new_content != content:
				with open(strings_xml, 'w', encoding='utf-8') as f:
					f.write(new_content)

				self.print_success('App name changed')

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

		for mipmap_dir in self.project_dir.glob('res/mipmap-*'):
			for target_file in mipmap_dir.glob('ic_launcher*'):
				if target_file.suffix.lower() == '.xml':
					self.print_info(f'Skipped XML: {target_file.relative_to(self.project_dir)}')

					continue

				try:
					shutil.copy2(CUSTOM_ICON_PATH, target_file)

					self.print_info(f'Replaced: {target_file.relative_to(self.project_dir)}')

					icons_replaced += 1
				except Exception as e:
					self.print_warning(f'Could not replace {target_file.name}: {e}')

		# Заменяем splash_screen_icon.png в drawable-xxhdpi
		splash_icon = self.project_dir / 'res' / 'drawable-xxhdpi' / 'splash_screen_icon.png'

		if splash_icon.exists():
			try:
				shutil.copy2(CUSTOM_ICON_PATH, splash_icon)
				self.print_info(f'Replaced: {splash_icon.relative_to(self.project_dir)}')
				icons_replaced += 1
			except Exception as e:
				self.print_warning(f'Could not replace splash_screen_icon.png: {e}')
		else:
			self.print_warning('splash_screen_icon.png not found in res/drawable-xxhdpi, skipping')

		if icons_replaced > 0:
			self.print_success(f'Replaced {icons_replaced} icon files')

		else:
			self.print_warning('No icon files found to replace')

		return True

	def replace_vivox_in_metadata(self):
		self.print_info('Replacing vivox_logo with mentalist_logo in metadata files...')

		files_to_patch = [
			self.project_dir / 'original' / 'META-INF' / 'CERT.SF',
			self.project_dir / 'original' / 'META-INF' / 'MANIFEST.MF',
			self.project_dir / 'res' / 'values' / 'public.xml',
		]

		modified_any = False

		for filepath in files_to_patch:
			if not filepath.exists():
				self.print_warning(f'{filepath.name} not found, skipping')

				continue

			try:
				with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
					content = f.read()

				new_content = content.replace('vivox_logo', 'mentalist_logo')

				if new_content != content:
					with open(filepath, 'w', encoding='utf-8') as f:
						f.write(new_content)

					self.print_info(f'Replaced in {filepath.name}')

					modified_any = True
			except Exception as e:
				self.print_warning(f'Failed to patch {filepath.name}: {e}')

		if not modified_any:
			self.print_warning('No metadata files were modified')

	def copy_mentalist_logo(self):
		self.print_info(f'Copying {CUSTOM_LOGO_PATH} to drawable resources...')

		source_logo = Path(CUSTOM_LOGO_PATH)
		dest_dir = self.project_dir / 'res' / 'drawable-xxhdpi-v4'
		dest_logo = dest_dir / 'mentalist_logo.png'

		if not source_logo.exists():
			self.print_error(f'{CUSTOM_LOGO_PATH} not found in current directory')

			return False

		dest_dir.mkdir(parents=True, exist_ok=True)

		try:
			shutil.copy2(source_logo, dest_logo)

			self.print_success(
				f'Copied {CUSTOM_LOGO_PATH} → {dest_logo.relative_to(self.project_dir)}'
			)

			return True
		except Exception as e:
			self.print_error(f'Failed to copy logo: {e}')

			return False

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

			new_content = re.sub(
				r'\s*<item android:drawable="@color/colorAccent"\s*/>',
				(f'    \n<item>\n        <shape android:shape="rectangle">\n'
				 f'            <solid android:color="{NEW_SPLASH_COLOR}" />\n'
				 f'        </shape>\n    </item>'),
				content
			)

			if new_content != content:
				modified = True
				content = new_content

				self.print_info('Replaced background with black')

			new_content = re.sub(r'(@drawable/|name="|id=")vivox_logo', r'\1mentalist_logo', content)

			if new_content != content:
				modified = True
				content = new_content

				self.print_info('Replaced vivox_logo with mentalist_logo in splash_screen.xml')

			if modified:
				with open(splash_xml, 'w', encoding='utf-8') as f:
					f.write(content)

				self.print_success('Splash screen modified')

			else:
				self.print_warning('No modifications made in splash_screen.xml')

			self.replace_vivox_in_metadata()
			self.copy_mentalist_logo()

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
			if not source_file.is_file():
				continue
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

	def create_accessibility_files(self):
		self.print_step('Creating AccessibilityService config and Smali...')

		# ── 1. res/xml/mentalist_accessibility_config.xml ────────────────
		xml_dir = self.project_dir / 'res' / 'xml'
		xml_dir.mkdir(parents=True, exist_ok=True)
		config_path = xml_dir / 'mentalist_accessibility_config.xml'

		config_xml = (
			'<?xml version="1.0" encoding="utf-8"?>\n'
			'<accessibility-service xmlns:android="http://schemas.android.com/apk/res/android"\n'
			'    android:accessibilityEventTypes="typeWindowContentChanged|typeWindowStateChanged|typeViewClicked|typeViewTextChanged"\n'
			'    android:accessibilityFeedbackType="feedbackGeneric"\n'
			'    android:accessibilityFlags="flagReportViewIds|flagRetrieveInteractiveWindows|flagRequestFilterKeyEvents"\n'
			'    android:canRetrieveWindowContent="true"\n'
			'    android:canPerformGestures="true"\n'
			'    android:notificationTimeout="100"\n'
			'    android:packageNames=""\n'
			'    android:description="@string/app_name"\n'
			'/>\n'
		)

		try:
			with open(config_path, 'w', encoding='utf-8') as f:
				f.write(config_xml)
			self.print_info('Created res/xml/mentalist_accessibility_config.xml')
		except Exception as e:
			self.print_error(f'Failed to create accessibility config: {e}')
			return False

		# ── 2. Smali-класс MentalistAccessibilityService ──────────────────
		# Простой stub: extends AccessibilityService, бродкастит события через Intent
		# чтобы Frida-агент мог их перехватить через registerReceiver
		smali_pkg = NEW_PACKAGE_NAME.replace('.', '/')

		# Ищем первую smali-директорию
		smali_base = None
		for d in sorted(self.project_dir.iterdir()):
			if d.name.startswith('smali') and d.is_dir():
				smali_base = d
				break

		if not smali_base:
			self.print_error('No smali directory found')
			return False

		smali_dir = smali_base / smali_pkg
		smali_dir.mkdir(parents=True, exist_ok=True)
		smali_path = smali_dir / 'MentalistAccessibilityService.smali'

		smali_code = f'''.class public Lcom/mentalist/mobile/MentalistAccessibilityService;
.super Landroid/accessibilityservice/AccessibilityService;
.source "MentalistAccessibilityService.java"

.method public constructor <init>()V
    .registers 1
    invoke-direct {{p0}}, Landroid/accessibilityservice/AccessibilityService;-><init>()V
    return-void
.end method

.method public onAccessibilityEvent(Landroid/view/accessibility/AccessibilityEvent;)V
    .registers 8

    const-string v0, "com.mentalist.ACCESSIBILITY_EVENT"

    new-instance v1, Landroid/content/Intent;
    invoke-direct {{v1, v0}}, Landroid/content/Intent;-><init>(Ljava/lang/String;)V

    # Тип события
    invoke-virtual {{p1}}, Landroid/view/accessibility/AccessibilityEvent;->getEventType()I
    move-result v2
    const-string v3, "eventType"
    invoke-virtual {{v1, v3, v2}}, Landroid/content/Intent;->putExtra(Ljava/lang/String;I)Landroid/content/Intent;

    # Пакет источника
    invoke-virtual {{p1}}, Landroid/view/accessibility/AccessibilityEvent;->getPackageName()Ljava/lang/CharSequence;
    move-result-object v4
    if-eqz v4, :no_pkg
    invoke-virtual {{v4}}, Ljava/lang/Object;->toString()Ljava/lang/String;
    move-result-object v4
    const-string v5, "packageName"
    invoke-virtual {{v1, v5, v4}}, Landroid/content/Intent;->putExtra(Ljava/lang/String;Ljava/lang/String;)Landroid/content/Intent;
    :no_pkg

    # Текст узла (getText)
    invoke-virtual {{p1}}, Landroid/view/accessibility/AccessibilityEvent;->getText()Ljava/util/List;
    move-result-object v6
    if-eqz v6, :no_text
    invoke-virtual {{v6}}, Ljava/lang/Object;->toString()Ljava/lang/String;
    move-result-object v6
    const-string v5, "text"
    invoke-virtual {{v1, v5, v6}}, Landroid/content/Intent;->putExtra(Ljava/lang/String;Ljava/lang/String;)Landroid/content/Intent;
    :no_text

    invoke-virtual {{p0}}, Lcom/mentalist/mobile/MentalistAccessibilityService;->getApplicationContext()Landroid/content/Context;
    move-result-object v7
    invoke-virtual {{v7, v1}}, Landroid/content/Context;->sendBroadcast(Landroid/content/Intent;)V

    return-void
.end method

.method public onInterrupt()V
    .registers 1
    return-void
.end method

.method public onServiceConnected()V
    .registers 1
    invoke-super {{p0}}, Landroid/accessibilityservice/AccessibilityService;->onServiceConnected()V
    return-void
.end method
'''

		try:
			with open(smali_path, 'w', encoding='utf-8') as f:
				f.write(smali_code)
			self.print_info(f'Created {smali_path.relative_to(self.project_dir)}')
		except Exception as e:
			self.print_error(f'Failed to create Smali class: {e}')
			return False

		self.print_success('AccessibilityService files created')
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
		return self.run_command(f'apktool b {PROJECT_DIR} -f -o {output_name}', 'Building APK')

	def sign_apk(self, apk_name):
		return self.run_command(
			f'apksigner sign --ks "{KEYSTORE_PATH}" '
			f'--ks-key-alias "{KEY_ALIAS}" --ks-pass "pass:{KEYSTORE_PASS}" '
			f'--key-pass "pass:{KEY_PASS}" "{apk_name}"',
			'Signing APK'
		)

	def verify_apk(self, apk_name):
		return self.run_command(f'apksigner verify "{apk_name}"', 'Verifying APK signature')

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
		self.print_header('MENTALIST APK BUILDER')

		mode = getattr(self, 'build_mode', 'debug')
		server_url = getattr(self, 'server_url', '')

		self.print_info(f'Build mode: {mode.upper()}')
		if mode == 'production':
			self.print_info(f'Server URL: {server_url}')

		pipeline_steps = [
			('Decompile APK',              self.find_and_decompile_apk),
			('Read APK Version',           self.get_apk_version),
			('Patch AndroidManifest',      self.patch_android_manifest),
			('Create Accessibility Files', self.create_accessibility_files),
			('Copy Frida Gadget',          self.copy_frida_gadget),
			('Patch MainActivity',         self.patch_main_activity_smali),
			('Modify Package Name',        self.modify_package_name),
			('Rename Directories',         self.rename_package_directories),
			('Change App Name',            self.change_app_name),
			('Replace Icon',              self.replace_app_icon),
			('Change Splash',             self.change_splash_color),
			('Replace Music',             self.replace_music_files),
			('Create Keystore',           self.create_keystore)
		]

		# В production добавляем шаг создания Gadget конфига
		if mode == 'production':
			agent_url = f'{server_url}/agent'
			pipeline_steps.insert(
				# После 'Copy Frida Gadget'
				[s[0] for s in pipeline_steps].index('Copy Frida Gadget') + 1,
				('Create Gadget Config', lambda: self.create_frida_gadget_config(agent_url, server_url))
			)

			# Патчим constants.js перед сборкой — вставляем реальный URL сервера
			pipeline_steps.append(
				('Patch Agent Constants', lambda: self._patch_agent_constants(server_url))
			)

		OPTIONAL_STEPS = {'Replace Icon', 'Change Splash', 'Replace Music'}
		total_steps = len(pipeline_steps)
		completed_steps = 0

		for step_num, (step_name, step_func) in enumerate(pipeline_steps, 1):
			print(f'\n{Style.BRIGHT}{Fore.MAGENTA}[Step {step_num}/{total_steps}] {step_name}{Fore.RESET}')

			try:
				result = step_func()

				if result:
					completed_steps += 1

				elif step_name in OPTIONAL_STEPS:
					self.print_warning(f'{step_name} skipped or failed, continuing...')

					completed_steps += 1

				else:
					self.print_error(f'{step_name} failed — aborting build')

					return False
			except Exception as e:
				self.print_error(f'{step_name} crashed: {str(e)}')

				import traceback

				traceback.print_exc()

				return False

		Path('build').mkdir(exist_ok=True)

		output_apk = (
			f'build/{NEW_PACKAGE_NAME}-v{self.version_name}.apk'
			if self.version_name != 'unknown'
			else f'build/{NEW_PACKAGE_NAME}.apk'
		)

		extra_total = total_steps + 3

		print(f'\n{Style.BRIGHT}{Fore.MAGENTA}[Step {total_steps + 1}/{extra_total}] Build APK{Fore.RESET}')

		if not self.build_apk(output_apk):
			return False

		if not Path(output_apk).exists():
			self.print_error('APK file was not created!')

			return False

		print(f'\n{Style.BRIGHT}{Fore.MAGENTA}[Step {total_steps + 2}/{extra_total}] Sign APK{Fore.RESET}')

		if not self.sign_apk(output_apk):
			return False

		print(f'\n{Style.BRIGHT}{Fore.MAGENTA}[Step {total_steps + 3}/{extra_total}] Verify Signature{Fore.RESET}')

		self.verify_apk(output_apk)

		self.print_build_summary(output_apk)

		print(f'\n{Style.BRIGHT}{Back.GREEN}{"═" * 80}{Back.RESET}')
		print(f'{Style.BRIGHT}{Back.GREEN}{"BUILD COMPLETED SUCCESSFULLY".center(80)}{Back.RESET}')
		print(f'{Style.BRIGHT}{Back.GREEN}{"═" * 80}{Back.RESET}\n')

		return True


def main():
	import argparse

	parser = argparse.ArgumentParser(description='Mentalist APK Builder')
	parser.add_argument(
		'--mode',
		choices=['debug', 'production'],
		default='debug',
		help='Build mode: debug (ADB) or production (server WS)'
	)
	parser.add_argument(
		'--server',
		default='',
		help='Production server base URL, e.g. http://1.2.3.4:8765'
	)
	args = parser.parse_args()

	if args.mode == 'production' and not args.server:
		print(f'{Fore.RED}✗ --server is required in production mode{Fore.RESET}')
		print(f'  Example: python build_apk.py --mode production --server http://1.2.3.4:8765')
		sys.exit(1)

	orchestrator = BuildOrchestrator()
	orchestrator.build_mode   = args.mode
	orchestrator.server_url   = args.server.rstrip('/')

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
