# Odonto Emille

Sistema web de agendamento odontológico desenvolvido como projeto educacional para uma estudante de Odontologia.

O projeto reúne uma página pública para pacientes, um painel protegido para a doutora e uma integração opcional com a WhatsApp Cloud API.

## Funcionalidades

- Agendamento de procedimentos e horários disponíveis.
- Prevenção de reservas duplicadas.
- Painel da doutora para visualizar e cancelar consultas.
- Proteção de formulários com token CSRF.
- Persistência em MySQL com SQLAlchemy.
- Integração opcional com WhatsApp Cloud API.
- Endpoint `/health` para monitoramento.
- Execução local e implantação com Docker/Elastic Beanstalk.

## Tecnologias

- Python e Flask
- SQLAlchemy e PyMySQL
- MySQL
- HTML e CSS
- Docker
- Waitress
- WhatsApp Cloud API

## Executar localmente

Requisitos: Python 3.10 ou superior e MySQL 8 ou compatível.

No PowerShell, dentro da pasta do projeto:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Crie o banco de dados:

```sql
CREATE DATABASE odontologia CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

Depois, preencha o `.env` com valores locais para `DATABASE_URL`, `SECRET_KEY`, `DOCTOR_USERNAME` e `DOCTOR_PASSWORD`.

Para iniciar:

```powershell
py run.py
```

Acesse <http://127.0.0.1:5000>.

O painel da doutora fica em `/doutora`.

## Testes

```powershell
pip install -r requirements-dev.txt
pytest
```

## Configuração da agenda

Os procedimentos e horários ficam em `config.py`:

- `PROCEDURES`: procedimentos exibidos aos pacientes.
- `WORKING_HOURS`: horários disponíveis por dia da semana.

Segunda-feira corresponde a `0` e domingo a `6`. Dias ausentes ficam fechados.

## WhatsApp Cloud API

A integração é opcional. Para mantê-la desativada, use:

```env
WHATSAPP_ENABLED=0
```

Para ativá-la, configure as credenciais da Meta no ambiente de hospedagem, nunca diretamente no código ou no repositório.

## Implantação

O projeto inclui `Dockerfile`, `Procfile` e servidor WSGI para implantação em serviços compatíveis, como o AWS Elastic Beanstalk.

Em produção:

- configure as variáveis de ambiente no painel da hospedagem;
- não publique o arquivo `.env`;
- use uma `SECRET_KEY` longa e aleatória;
- use uma senha exclusiva para o painel;
- mantenha `FLASK_DEBUG=0`;
- use HTTPS;
- faça backups e proteja os dados dos pacientes conforme a LGPD.

## Observações

Este é um projeto educacional e não representa uma clínica comercial. O sistema ainda não envia lembretes nem permite cancelamento ou alteração de agendamentos pelo paciente.
