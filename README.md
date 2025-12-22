# D2R loader

## git 설정

git init
git remote add origin https://github.com/cihkill3/D2R_Loader.git
git add .
git commit -m "설명"
git branch -M master
git push -u origin master


## 1. 깃허브 내용을 강제로 가져와서 합치기
git pull origin master --allow-unrelated-histories


## 2. (합쳐진 후) 다시 올리기
git push -u origin master




# .gitignore
__pycache__/
build/
dist/
*.spec
venv/
.idea/
.vscode/
*.user
config.json



# build
pyinstaller --noconsole --onefile --icon=app_icon.ico --add-data "app_icon.ico;." --name="D2R_Loader" d2rloader.py
