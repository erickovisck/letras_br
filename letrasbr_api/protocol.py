import sys
import os

def register_protocol():
    """Registra o protocolo personalizado letrasbr:// no Windows para permitir inicialização com 1 clique do navegador."""
    if sys.platform != "win32":
        return False

    try:
        import winreg
        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        bat_path = os.path.join(root_dir, "iniciar_servidor.bat")

        if not os.path.exists(bat_path):
            return False

        cmd_str = f'cmd.exe /c start "" "{bat_path}"'

        key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\letrasbr")
        winreg.SetValue(key, "", winreg.REG_SZ, "URL:LetrasBR Protocol")
        winreg.SetValueEx(key, "URL Protocol", 0, winreg.REG_SZ, "")

        cmd_key = winreg.CreateKey(key, r"shell\open\command")
        winreg.SetValue(cmd_key, "", winreg.REG_SZ, cmd_str)

        winreg.CloseKey(cmd_key)
        winreg.CloseKey(key)
        print("[Protocol] Protocolo 'letrasbr://' registrado com sucesso no Windows!")
        return True
    except Exception as e:
        print(f"[Protocol] Erro ao registrar protocolo: {e}")
        return False

if __name__ == "__main__":
    register_protocol()
