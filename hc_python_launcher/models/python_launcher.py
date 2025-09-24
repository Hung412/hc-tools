import subprocess
import os
from odoo import models, fields, api
from odoo.exceptions import UserError

class PythonLauncher(models.TransientModel):
    _name = 'python.launcher'
    _description = 'Python File Launcher'
    
    script_name = fields.Selection([
        ('btmc_launcher', 'BTMC Launcher'),
        ('custom', 'Custom Script'),
    ], string='Script to Run', default='btmc_launcher', required=True)
    
    custom_script_path = fields.Char(
        string='Custom Script Path',
        help='Full path to Python script (e.g., C:\\path\\to\\script.py)'
    )
    
    run_mode = fields.Selection([
        ('background', 'Background (No wait for result)'),
        ('wait', 'Wait (Wait for result and display)'),
    ], string='Run Mode', default='background', required=True)
    
    @api.onchange('script_name')
    def _onchange_script_name(self):
        """Auto set path for BTMC Launcher"""
        if self.script_name == 'btmc_launcher':
            self.custom_script_path = r"C:\Users\ADMIN\git\hc_tools\btmc_launcher.py"
        else:
            self.custom_script_path = ''
    
    def _get_script_path(self):
        """Get script path to run"""
        if self.script_name == 'btmc_launcher':
            return r"C:\Users\ADMIN\git\hc_tools\btmc_launcher.py"
        elif self.script_name == 'custom' and self.custom_script_path:
            return self.custom_script_path
        else:
            raise UserError("Please select a script or enter path!")
    
    def action_run_script_background(self):
        """Run script in background"""
        try:
            script_path = self._get_script_path()
            
            # Check if file exists
            if not os.path.exists(script_path):
                raise UserError(f"File not found: {script_path}")
            
            # Run Python file in background
            process = subprocess.Popen(
                ['python', script_path],
                cwd=os.path.dirname(script_path),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == 'nt' else 0
            )
            
            script_name = os.path.basename(script_path)
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Success',
                    'message': f'Successfully launched {script_name}! (PID: {process.pid})',
                    'type': 'success',
                    'sticky': False,
                }
            }
            
        except Exception as e:
            raise UserError(f"Error running script: {str(e)}")
    
    def action_run_script_wait(self):
        """Run script and wait for result"""
        try:
            script_path = self._get_script_path()
            
            if not os.path.exists(script_path):
                raise UserError(f"File not found: {script_path}")
            
            # Run and wait for result (with timeout)
            result = subprocess.run(
                ['python', script_path],
                cwd=os.path.dirname(script_path),
                capture_output=True,
                text=True,
                timeout=60  # Timeout after 60 seconds
            )
            
            script_name = os.path.basename(script_path)
            
            if result.returncode == 0:
                message = f"{script_name} executed successfully!"
                if result.stdout:
                    message += f"\n\nOutput:\n{result.stdout[:500]}"
                msg_type = 'success'
            else:
                message = f"{script_name} encountered error!"
                if result.stderr:
                    message += f"\n\nError:\n{result.stderr[:500]}"
                msg_type = 'warning'
                
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Result',
                    'message': message,
                    'type': msg_type,
                    'sticky': True,
                }
            }
            
        except subprocess.TimeoutExpired:
            raise UserError("Script took too long (timeout 60s)")
        except Exception as e:
            raise UserError(f"Error running script: {str(e)}")
    
    def action_run_script(self):
        """Run script according to selected mode"""
        if self.run_mode == 'background':
            return self.action_run_script_background()
        else:
            return self.action_run_script_wait()
    
    def action_quick_launch_btmc(self):
        """Quick launch BTMC Launcher"""
        self.script_name = 'btmc_launcher'
        self.run_mode = 'background'
        return self.action_run_script_background()
