# 🔧 Troubleshooting - Solução de Problemas

## ❌ Erro: `ModuleNotFoundError: No module named 'loader'` ao rodar pytest

### Sintoma
```
ERROR tests/test_loader.py - ModuleNotFoundError: No module named 'loader'
ERROR tests/test_model.py - ModuleNotFoundError: No module named 'model'
ERROR tests/test_scorer.py - ModuleNotFoundError: No module named 'scorer'
```

### Causa
O pytest não consegue encontrar os módulos porque está sendo executado de um diretório onde a raiz do projeto não está no `PYTHONPATH`.

### ✅ Solução (JÁ IMPLEMENTADA)

Adicionamos dois arquivos de configuração:

1. **`tests/conftest.py`** - Arquivo automático do pytest que adiciona o diretório pai ao sys.path
2. **`pytest.ini`** - Configuração do pytest

Esses arquivos já estão no projeto, então agora é só rodar:

```bash
source venv/bin/activate
pytest
```

### Se ainda assim tiver problemas

**Opção 1: Rodar do diretório raiz do projeto**
```bash
cd /home/jeff/Documentos/dev/peer-eval
source venv/bin/activate
pytest
```

**Opção 2: Usar python -m pytest (mais explícito)**
```bash
source venv/bin/activate
python -m pytest tests/ -v
```

**Opção 3: Adicionar ao PYTHONPATH manualmente**
```bash
export PYTHONPATH=/home/jeff/Documentos/dev/peer-eval:$PYTHONPATH
pytest
```

---

## ❌ Erro: `venv not found` ao tentar ativar

### Sintoma
```bash
./activate.sh
bash: ./activate.sh: No such file or directory
```

### Solução
1. Certifique-se de que está no diretório correto:
   ```bash
   cd /home/jeff/Documentos/dev/peer-eval
   ```

2. Se o arquivo não existe, recrie-o:
   ```bash
   python -m venv venv
   ```

3. Ative manualmente:
   ```bash
   source venv/bin/activate
   ```

---

## ❌ Erro: `ModuleNotFoundError` ao rodar main.py

### Sintoma
```
ModuleNotFoundError: No module named 'config'
```

### Causa
Você não ativou o venv ou está rodando de um diretório errado.

### Solução
```bash
# 1. Certifique-se de estar na raiz do projeto
cd /home/jeff/Documentos/dev/peer-eval

# 2. Ative o venv
source venv/bin/activate

# 3. Rode o projeto
python main.py --fixture fixtures/mr_artifacts.json \
               --members ana bruno carla diego \
               --deadline 2024-11-29T23:59:00Z
```

---

## ❌ Erro: `pip: command not found`

### Sintoma
```
pip: command not found
```

### Causa
O venv não está ativado.

### Solução
```bash
source venv/bin/activate
pip install -r requirements.txt
```

---

## ❌ Erro: `python: command not found`

### Sintoma
```
python: command not found
```

### Solução (Linux/macOS)
```bash
python3 main.py ...
# ou
source venv/bin/activate && python main.py ...
```

---

## ✅ Verificar que tudo está OK

```bash
# 1. Ativar venv
source venv/bin/activate

# 2. Verificar Python
python --version  # Deve mostrar Python 3.8+

# 3. Rodar testes
pytest -q  # Deve mostrar: 61 passed

# 4. Rodar projeto
python main.py --fixture fixtures/mr_artifacts.json \
               --members ana bruno carla diego \
               --deadline 2024-11-29T23:59:00Z
```

Se todos os passos acima funcionarem, está tudo OK! ✅

---

## 📞 Ajuda Adicional

Se ainda tiver problemas:

1. Verifique que está no diretório correto:
   ```bash
   pwd  # Deve mostrar: .../peer-eval
   ```

2. Verifique que o venv está ativado:
   ```bash
   which python  # Deve mostrar: .../venv/bin/python
   ```

3. Verifique que os arquivos estão lá:
   ```bash
   ls -la | grep -E '(config|model|loader|scorer)'
   ```

4. Limpe o cache do pytest:
   ```bash
   pytest --cache-clear
   ```

