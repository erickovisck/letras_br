using System;
using System.Diagnostics;
using System.IO;
using System.Windows.Forms;

namespace LetrasBR
{
    static class Program
    {
        [STAThread]
        static void Main()
        {
            try
            {
                string baseDir = AppDomain.CurrentDomain.BaseDirectory;
                string venvPythonw = Path.Combine(baseDir, ".venv", "Scripts", "pythonw.exe");
                string venvPython = Path.Combine(baseDir, ".venv", "Scripts", "python.exe");
                string runApiScript = Path.Combine(baseDir, "run_api.py");
                string configBat = Path.Combine(baseDir, "configurar_ambiente.bat");

                string targetPython = null;
                if (File.Exists(venvPythonw))
                {
                    targetPython = venvPythonw;
                }
                else if (File.Exists(venvPython))
                {
                    targetPython = venvPython;
                }

                // Se o ambiente virtual .venv nao existir, executa o configurador
                if (targetPython == null || !File.Exists(runApiScript))
                {
                    if (File.Exists(configBat))
                    {
                        var res = MessageBox.Show(
                            "O ambiente virtual (.venv) ainda nao foi configurado.\nDeseja executar o instalador agora?",
                            "LetrasBR - Configuracao Necessaria",
                            MessageBoxButtons.YesNo,
                            MessageBoxIcon.Question
                        );

                        if (res == DialogResult.Yes)
                        {
                            ProcessStartInfo batPsi = new ProcessStartInfo
                            {
                                FileName = "cmd.exe",
                                Arguments = "/c \"" + configBat + "\"",
                                WorkingDirectory = baseDir,
                                UseShellExecute = true
                            };
                            Process.Start(batPsi);
                        }
                        return;
                    }
                    else
                    {
                        MessageBox.Show(
                            "Arquivos de inicializacao nao foram encontrados em:\n" + baseDir,
                            "LetrasBR - Erro",
                            MessageBoxButtons.OK,
                            MessageBoxIcon.Error
                        );
                        return;
                    }
                }

                // Inicia o processo desanexado do launcher
                ProcessStartInfo psi = new ProcessStartInfo
                {
                    FileName = targetPython,
                    Arguments = "\"" + runApiScript + "\"",
                    WorkingDirectory = baseDir,
                    UseShellExecute = true,
                    WindowStyle = ProcessWindowStyle.Hidden
                };

                Process.Start(psi);
            }
            catch (Exception ex)
            {
                MessageBox.Show(
                    "Ocorreu um erro ao iniciar o LetrasBR:\n\n" + ex.Message,
                    "LetrasBR - Falha na Inicializacao",
                    MessageBoxButtons.OK,
                    MessageBoxIcon.Error
                );
            }
        }
    }
}
