module.exports = {
  apps: [
    {
      name: 'techannel-backend',
      cwd: __dirname,
      script: 'venv/Scripts/python.exe',
      args: '-m techannel_push',
      interpreter: 'none',
      env: {
        PYTHONIOENCODING: 'utf-8',
        PYTHONUNBUFFERED: '1'
      },
      watch: false,
      autorestart: true,
      max_restarts: 10,
      restart_delay: 3000,
      log_date_format: 'YYYY-MM-DD HH:mm:ss',
      error_file: 'logs/backend-error.log',
      out_file: 'logs/backend-out.log',
      merge_logs: true
    },
    {
      name: 'techannel-frontend',
      cwd: __dirname + '/web',
      script: 'node_modules/vite/bin/vite.js',
      interpreter: 'node',
      env: {
        NODE_ENV: 'development'
      },
      watch: false,
      autorestart: true,
      max_restarts: 10,
      restart_delay: 3000,
      log_date_format: 'YYYY-MM-DD HH:mm:ss',
      error_file: '../logs/frontend-error.log',
      out_file: '../logs/frontend-out.log',
      merge_logs: true
    }
  ]
};
