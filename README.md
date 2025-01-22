# Apollo Contact Assistant

## Local Setup

1. Install pipenv if you haven't already:

```bash
pip install pipenv
```

2. Install the dependencies:

```bash
pipenv install

```
3. Create a .env file with the following variables:

```bash
APOLLO_API_KEY="your_apollo_api_key"
```

4. Comment the line in main.py that uses the secrets.toml file:

```python
#api_key = st.secrets["APOLLO_API_KEY"]
```

5. Run the app locally:

```bash
pipenv run streamlit run main.py
```