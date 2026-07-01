import shutil
import subprocess
import sys
import hashlib
import random
import base64
import json
from pathlib import Path
from datetime import datetime
from colorama import Fore, Style, Back, init

try:
    from Cython.Build import cythonize
    from setuptools import setup, Extension

    HAS_CYTHON = True
except ImportError:
    HAS_CYTHON = False

init(autoreset=True)


class JSEncryptor:
    @staticmethod
    def generate_encryption_key():
        return hashlib.sha256(str(random.random()).encode()).hexdigest()
    
    @staticmethod
    def encrypt_js(js_content, encryption_key):
        key_bytes = bytes.fromhex(encryption_key)
        js_bytes = js_content.encode('utf-8')
        
        xor_encrypted = bytes([
            b ^ key_bytes[i % len(key_bytes)] 
            for i, b in enumerate(js_bytes)
        ])

        b64_encrypted = base64.b64encode(xor_encrypted)

        salt = hashlib.sha256(str(random.random()).encode()).digest()
        salted = salt + b64_encrypted

        final_encrypted = base64.b64encode(salted).decode('utf-8')
        
        return final_encrypted, len(salt)
    
    @staticmethod
    def create_decryption_decorator():
        decorator_code = '''
import base64
import hashlib
from functools import wraps

def _decrypt_protected_js(encrypted_payload, decryption_key, salt_length):
    try:
        final_decoded = base64.b64decode(encrypted_payload.encode('utf-8'))

        salt = final_decoded[:salt_length]
        b64_encrypted = final_decoded[salt_length:]

        xor_encrypted = base64.b64decode(b64_encrypted)

        key_bytes = bytes.fromhex(decryption_key)
        js_bytes = bytes([
            b ^ key_bytes[i % len(key_bytes)]
            for i, b in enumerate(xor_encrypted)
        ])
        
        return js_bytes.decode('utf-8')
    except Exception as e:
        return "console.log('Agent initialized');"

def protected_js_loader(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        from auth_protection import _integrity_checker
        
        if not _integrity_checker.verify_integrity():
            corruption_handler = _integrity_checker.get_corruption_handler()
            
            if corruption_handler.is_phantom_mode():
                return "console.log('Agent running in phantom mode');"

        from auth_protection import _global_protection
        
        encrypted_payload = _global_protection.get_key('js_encrypted_payload')
        decryption_key = _global_protection.get_key('js_decryption_key')
        salt_length = _global_protection.get_key('js_salt_length')
        
        if not all([encrypted_payload, decryption_key, salt_length]):
            return func(*args, **kwargs)

        try:
            salt_length = int(salt_length)
            decrypted_js = _decrypt_protected_js(
                encrypted_payload,
                decryption_key,
                salt_length
            )
            
            return decrypted_js
        except:
            return func(*args, **kwargs)
    
    return wrapper
'''
        return decorator_code


class IntegrityManager:
    def __init__(self):
        self.py_hashes = {}
        self.pyd_hashes = {}
        self.target_files = []
        self.entanglement_key = None
        self.js_encryption_key = None
        self.js_encrypted_payload = None
        self.js_salt_length = None
    
    def calculate_hash(self, filepath):
        if not filepath.exists():
            return

        sha256 = hashlib.sha256()

        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                sha256.update(chunk)

        return sha256.hexdigest()
    
    def register_py_file(self, filepath, module_name):
        file_hash = self.calculate_hash(filepath)

        if file_hash:
            self.py_hashes[module_name] = file_hash
            self.target_files.append(module_name)

            return True

        return False
    
    def register_pyd_file(self, filepath, module_name):
        file_hash = self.calculate_hash(filepath)

        if file_hash:
            self.pyd_hashes[module_name] = file_hash

            return True

        return False
    
    def encrypt_js_file(self, js_filepath):
        if not js_filepath.exists():
            return False
        
        try:
            with open(js_filepath, 'r', encoding='utf-8') as f:
                js_content = f.read()

            self.js_encryption_key = JSEncryptor.generate_encryption_key()

            self.js_encrypted_payload, self.js_salt_length = JSEncryptor.encrypt_js(
                js_content,
                self.js_encryption_key
            )
            
            return True
        except Exception as e:
            print(f'Error encrypting JS: {e}')

            return False
    
    def generate_entanglement_key(self):
        combined_hash = hashlib.sha256()

        all_hashes = list(self.py_hashes.values()) + list(self.pyd_hashes.values())

        if self.js_encrypted_payload:
            all_hashes.append(hashlib.sha256(self.js_encrypted_payload.encode()).hexdigest())
        
        for file_hash in sorted(all_hashes):
            combined_hash.update(file_hash.encode())
        
        self.entanglement_key = combined_hash.hexdigest()

        return self.entanglement_key
    
    def inject_into_protection(self, protection_path):
        if not protection_path.exists():
            return False
        
        content = protection_path.read_text(encoding='utf-8')
        
        marker = '_integrity_checker = IntegrityChecker()'
        
        if marker not in content:
            return False
        
        clean_content = content.split(marker)[0] + marker + '\n'
        
        hash_injection = ''

        for module_name, file_hash in self.py_hashes.items():
            if 'auth_protection' in module_name:
                continue
            
            hash_injection += f"_integrity_checker.add_file('{module_name}', '{file_hash}')\n"

        for module_name, file_hash in self.pyd_hashes.items():
            if 'auth_protection' in module_name:
                continue
            
            hash_injection += f"_integrity_checker.add_pyd_file('{module_name}', '{file_hash}')\n"

        if self.entanglement_key:
            hash_injection += f"_integrity_checker.set_entanglement_key('{self.entanglement_key}')\n"

        if all([self.js_encrypted_payload, self.js_encryption_key, self.js_salt_length]):
            hash_injection += f"_global_protection.store_key('js_encrypted_payload', '''{self.js_encrypted_payload}''')\n"
            hash_injection += f"_global_protection.store_key('js_decryption_key', '{self.js_encryption_key}')\n"
            hash_injection += f"_global_protection.store_key('js_salt_length', '{self.js_salt_length}')\n"
        
        protection_path.write_text(clean_content + hash_injection, encoding='utf-8')
        
        return True


class MobileBuildOrchestrator:
    def __init__(self):
        self.project_root = Path.cwd()
        self.temp_build_env = self.project_root / 'build_env_temp'
        self.dist_dir = self.project_root / 'dist_mobile'
        self.build_dir = self.project_root / 'build_mobile'
        self.releases_dir = self.project_root / 'releases_mobile'
        
        self.version = '1.0.0'
        self.build_timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        self.protection_modules = [
            'server/auth_client.py',
            'server/auth_decorator.py',
            'server/auth_protection.py'
        ]
        
        self.core_modules = [
            'server/run_mod.py'
        ]
        
        self.additional_files = [
            'agent.js'
        ]
        
        self.integrity_manager = IntegrityManager()
    
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
    
    def check_environment(self):
        self.print_step('Checking build environment...')
        
        if not HAS_CYTHON:
            self.print_error('Cython not installed')

            return False
        
        self.print_success('Cython detected')

        try:
            import frida

            self.print_success('Frida detected')
        except ImportError:
            self.print_warning('Frida not installed - required for mobile runtime')
        
        return True
    
    def clean_workspace(self):
        self.print_step('Cleaning workspace...')
        
        dirs_to_clean = [self.dist_dir, self.build_dir, self.temp_build_env]

        for directory in dirs_to_clean:
            if directory.exists():
                shutil.rmtree(directory)

                self.print_info(f'Removed {directory.name}/')
        
        for pattern in ['*.pyd', '*.so', '*.spec', '*.c']:
            for file in self.project_root.glob(pattern):
                try:
                    file.unlink()

                    self.print_info(f'Removed {file.name}')
                except:
                    pass
        
        self.dist_dir.mkdir(exist_ok=True)
        self.releases_dir.mkdir(exist_ok=True)
        
        self.print_success('Workspace cleaned')
        
        return True
    
    def create_build_sandbox(self):
        self.print_step('Creating build sandbox...')
        
        if self.temp_build_env.exists():
            shutil.rmtree(self.temp_build_env)
        
        self.temp_build_env.mkdir(parents=True, exist_ok=True)

        for module in self.protection_modules:
            src = self.project_root / module

            if src.exists():
                shutil.copy2(src, self.temp_build_env / src.name)

                self.print_info(f'Copied: {module}')

        for module in self.core_modules:
            src = self.project_root / module

            if src.exists():
                shutil.copy2(src, self.temp_build_env / src.name)

                self.print_info(f'Copied: {module}')

        for filename in self.additional_files:
            src = self.project_root / filename

            if src.exists():
                shutil.copy2(src, self.temp_build_env / src.name)

                self.print_info(f'Copied: {filename}')
        
        self.print_success(f'Build sandbox created at: {self.temp_build_env}')

        return True
    
    def inject_js_protection(self):
        self.print_step('Injecting JS protection layer...')
        
        run_mod_path = self.temp_build_env / 'run_mod.py'
        
        if not run_mod_path.exists():
            self.print_error('run_mod.py not found')

            return False

        agent_js_path = self.temp_build_env / 'agent.js'
        
        if not agent_js_path.exists():
            self.print_warning('agent.js not found, skipping JS encryption')

            return True
        
        if not self.integrity_manager.encrypt_js_file(agent_js_path):
            self.print_error('Failed to encrypt agent.js')

            return False
        
        self.print_success(f'agent.js encrypted (key: {self.integrity_manager.js_encryption_key[:16]}...)')

        content = run_mod_path.read_text(encoding='utf-8')

        if 'protected_js_loader' in content:
            self.print_warning('JS protection already injected')

            return True

        decorator_code = JSEncryptor.create_decryption_decorator()

        import_section_end = content.find('\ninit(autoreset=True)')
        
        if import_section_end == -1:
            self.print_error('Could not find import section in run_mod.py')

            return False

        new_content = (
            content[:import_section_end] +
            '\ninit(autoreset=True)\n\n' +
            '# === PROTECTED JS LOADER DECORATOR ===\n' +
            decorator_code +
            '\n# === END PROTECTED JS LOADER ===\n' +
            content[import_section_end + len('\ninit(autoreset=True)'):]
        )
        
        load_script_marker = 'def load_script():'
        
        if load_script_marker in new_content:
            new_content = new_content.replace(
                load_script_marker,
                '@protected_js_loader\n' + load_script_marker
            )
            
            self.print_success('Added @protected_js_loader decorator to load_script()')
        
        else:
            self.print_warning('load_script() function not found')
        
        run_mod_path.write_text(new_content, encoding='utf-8')
        
        self.print_success('JS protection layer injected')
        
        return True
    
    def calculate_hashes(self):
        self.print_step('Calculating integrity hashes...')

        for module in self.protection_modules + self.core_modules:
            module_path = self.temp_build_env / Path(module).name

            if module_path.exists():
                self.integrity_manager.register_py_file(module_path, Path(module).name)
                
                file_hash = self.integrity_manager.py_hashes.get(Path(module).name)
                
                if file_hash:
                    self.print_info(f'{module}: {file_hash[:16]}...')
        
        return True
    
    def compile_protection_modules(self):
        self.print_step('Compiling protection modules...')
        
        # Cython компилирует уже скопированные плоские файлы в temp sandbox
        flat_modules = [Path(m).name for m in self.protection_modules]

        setup_code = f'''
from setuptools import setup
from Cython.Build import cythonize

setup(
    ext_modules=cythonize(
        {flat_modules},
        compiler_directives={{
            'language_level': '3',
            'always_allow_keywords': True,
            'emit_code_comments': False,
            'boundscheck': False,
            'wraparound': False,
            'cdivision': True,
            'embedsignature': False
        }},
        force=True
    ),
    script_args=['build_ext', '--inplace']
)
        '''
        
        setup_file = self.temp_build_env / f'setup_protection_{random.randint(1000, 9999)}.py'
        setup_file.write_text(setup_code)
        
        try:
            result = subprocess.run(
                [sys.executable, str(setup_file)],
                capture_output=True,
                text=True,
                cwd=str(self.temp_build_env),
                timeout=300
            )
            
            if result.returncode != 0:
                self.print_error(f'Compilation failed:\n{result.stderr}')

                return False

            for module in self.protection_modules:
                base_name = Path(module).stem

                pyd_files = list(self.temp_build_env.glob(f'{base_name}*.pyd'))
                so_files  = list(self.temp_build_env.glob(f'{base_name}*.so'))
                
                compiled_files = pyd_files + so_files
                
                if compiled_files:
                    compiled_file = compiled_files[0]
                    
                    self.integrity_manager.register_pyd_file(compiled_file, base_name)
                    
                    pyd_hash = self.integrity_manager.pyd_hashes.get(base_name)
                    
                    if pyd_hash:
                        self.print_success(f'Compiled {compiled_file.name}: {pyd_hash[:16]}...')
               
                else:
                    self.print_warning(f'No compiled file found for {base_name}')

            c_files = list(self.temp_build_env.glob('*.c'))
            
            for c_file in c_files:
                try:
                    c_file.unlink()
                except:
                    pass
            
            self.print_success('Protection modules compiled successfully')
            
            return True
            
        except subprocess.TimeoutExpired:
            self.print_error('Compilation timeout')

            return False
        except Exception as e:
            self.print_error(f'Compilation error: {e}')

            return False
        finally:
            if setup_file.exists():
                try:
                    setup_file.unlink()
                except:
                    pass
    
    def finalize_integrity_system(self):
        self.print_step('Finalizing integrity system...')

        entanglement_key = self.integrity_manager.generate_entanglement_key()

        self.print_success(f'Entanglement key: {entanglement_key[:16]}...')
        
        protection_path = self.temp_build_env / 'auth_protection.py'
        
        if protection_path.exists():
            if self.integrity_manager.inject_into_protection(protection_path):
                self.print_success('Integrity system injected into auth_protection.py')
            
            else:
                self.print_error('Failed to inject integrity system')

                return False

        else:
            self.print_error('auth_protection.py not found')

            return False
        
        return True
    
    def create_distribution(self):
        self.print_step('Creating distribution package...')
        
        release_name = f'Mentalist_Mobile_v{self.version}_{self.build_timestamp}'
        release_path = self.releases_dir / release_name
        release_path.mkdir(parents=True, exist_ok=True)

        for item in self.temp_build_env.iterdir():
            if item.suffix in ['.pyd', '.so', '.py', '.js', '.txt']:
                if item.suffix == '.py' and item.stem in [Path(m).stem for m in self.protection_modules]:
                    compiled_exists = any(
                        self.temp_build_env.glob(f'{item.stem}*.pyd')
                    ) or any(
                        self.temp_build_env.glob(f'{item.stem}*.so')
                    )

                    if compiled_exists:
                        self.print_info(f'Skipped {item.name} (compiled version exists)')
                        
                        continue
                
                shutil.copy2(item, release_path / item.name)

                self.print_info(f'Added: {item.name}')

        manifest = {
            'version': self.version,
            'build_date': datetime.now().isoformat(),
            'build_timestamp': self.build_timestamp,
            'protection_layers': [
                'Total Compilation (Cython)',
                'JS Encryption (Multi-Layer)',
                'Runtime JS Decryption',
                'Distributed Integrity Checks (PY + PYD)',
                'Mathematical Entanglement',
                'Anti-Debug Protection',
                'SSL Certificate Pinning',
                'Silent Failure Protocol'
            ],
            'files': [f.name for f in release_path.iterdir()],
            'js_encrypted': bool(self.integrity_manager.js_encrypted_payload)
        }
        
        manifest_path = release_path / 'build_manifest.json'

        with open(manifest_path, 'w', encoding='utf-8') as f:
            json.dump(manifest, f, indent=2)
        
        self.print_success('Created build manifest')

        archive_name = f'{release_name}.zip'
        archive_path = self.releases_dir / archive_name
        
        shutil.make_archive(
            str(archive_path.with_suffix('')),
            'zip',
            release_path
        )
        
        self.print_success(f'Created archive: {archive_name}')
        
        return release_path, archive_path
    
    def cleanup_sandbox(self):
        self.print_step('Cleaning temporary files...')
        
        if self.temp_build_env.exists():
            shutil.rmtree(self.temp_build_env)

            self.print_info('Removed build sandbox')
        
        if self.build_dir.exists():
            shutil.rmtree(self.build_dir)

            self.print_info('Removed build directory')
        
        self.print_success('Cleanup complete')

        return True
    
    def print_build_summary(self, release_path, archive_path):
        self.print_header('BUILD SUMMARY')
        
        print(f'{Fore.CYAN}Version:{Fore.RESET} {Style.BRIGHT}{self.version}{Style.RESET_ALL}')
        print(f'{Fore.CYAN}Build Time:{Fore.RESET} {self.build_timestamp}')
        print(f'{Fore.CYAN}Protection Layers:{Fore.RESET}')
        print(f'  • Total Compilation (Cython)')
        print(f'  • JS Encryption (Multi-Layer XOR + Base64 + Salt)')
        print(f'  • Runtime JS Decryption (Protected Decorator)')
        print(f'  • Distributed Integrity Checks (PY + PYD)')
        print(f'  • Mathematical Entanglement')
        print(f'  • Anti-Debug Protection')
        print(f'  • SSL Certificate Pinning')
        print(f'  • Silent Failure Protocol')
        
        if self.integrity_manager.js_encrypted_payload:
            print(f'\n{Style.BRIGHT}{Fore.GREEN}JS Protection:{Fore.RESET}')
            print(f'  • Encryption Key: {self.integrity_manager.js_encryption_key[:16]}...')
            print(f'  • Payload Size: {len(self.integrity_manager.js_encrypted_payload)} bytes')
            print(f'  • Salt Length: {self.integrity_manager.js_salt_length} bytes')
        
        print(f'\n{Style.BRIGHT}{Fore.GREEN}Release Contents:{Fore.RESET}')
        
        if release_path and release_path.exists():
            for item in sorted(release_path.iterdir()):
                if item.is_file():
                    size_kb = item.stat().st_size / 1024

                    print(f'  • {item.name:<40} ({size_kb:>6.2f} KB)')
        
        print(f'\n{Fore.YELLOW}Release Location:{Fore.RESET}')

        if release_path:
            print(f'  {release_path}')
        
        print(f'\n{Fore.YELLOW}Archive Location:{Fore.RESET}')

        if archive_path:
            print(f'  {archive_path}')
    
    def execute_build_pipeline(self):
        self.print_header(f'MENTALIST MOBILE BUILD SYSTEM v{self.version}')
        
        pipeline_steps = [
            ('Environment Check', self.check_environment),
            ('Workspace Cleanup', self.clean_workspace),
            ('Build Sandbox Creation', self.create_build_sandbox),
            ('JS Protection Injection', self.inject_js_protection),
            ('Hash Calculation', self.calculate_hashes),
            ('Protection Compilation', self.compile_protection_modules),
            ('Integrity Finalization', self.finalize_integrity_system),
            ('Distribution Package', self.create_distribution),
            ('Sandbox Cleanup', self.cleanup_sandbox)
        ]
        
        total_steps = len(pipeline_steps)
        completed_steps = 0
        
        release_path = None
        archive_path = None
        
        for step_num, (step_name, step_func) in enumerate(pipeline_steps, 1):
            print(f'\n{Style.BRIGHT}{Fore.MAGENTA}[Step {step_num}/{total_steps}] {step_name}{Fore.RESET}')
            
            try:
                if step_name == 'Distribution Package':
                    result = step_func()

                    if result and len(result) == 2:
                        release_path, archive_path = result

                        if release_path and archive_path:
                            completed_steps += 1

                        else:
                            self.print_error(f'{step_name} failed')

                            break

                    else:
                        self.print_error(f'{step_name} failed')

                        break

                else:
                    result = step_func()

                    if result:
                        completed_steps += 1

                    else:
                        self.print_error(f'{step_name} failed')

                        break
            except Exception as e:
                self.print_error(f'{step_name} crashed: {str(e)}')

                import traceback

                traceback.print_exc()

                break
        
        success = (completed_steps >= total_steps - 1)
        
        if success:
            self.print_build_summary(release_path, archive_path)
            
            print(f'\n{Style.BRIGHT}{Back.GREEN}{"═" * 80}{Back.RESET}')
            print(f'{Style.BRIGHT}{Back.GREEN}{"BUILD COMPLETED SUCCESSFULLY".center(80)}{Back.RESET}')
            print(f'{Style.BRIGHT}{Back.GREEN}{"═" * 80}{Back.RESET}\n')

        else:
            print(f'\n{Style.BRIGHT}{Back.RED}{"═" * 80}{Back.RESET}')
            print(f'{Style.BRIGHT}{Back.RED}{"BUILD FAILED".center(80)}{Back.RESET}')
            print(f'{Style.BRIGHT}{Back.RED}{"═" * 80}{Back.RESET}\n')
        
        return success


def main():
    orchestrator = MobileBuildOrchestrator()
    
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
