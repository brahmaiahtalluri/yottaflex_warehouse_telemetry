# Step-by-Step Guide: Run on Your Laptop, Push to GitHub & Share a Working Live Link

Follow these exact steps after downloading and extracting `yottaflex-warehouse-telemetry-challenge.zip` on your laptop.

---

## Step 1: Extract the ZIP Folder & Test Locally

1. Unzip `yottaflex-warehouse-telemetry-challenge.zip` into a folder on your laptop (for example `yottaflex-warehouse-telemetry`).
2. Open a terminal inside the extracted `yottaflex-warehouse-telemetry` directory.

### 1A. Verify the Synthetic Data Generator & Validator (Steps 1–10)
```bash
python3 generator/generate_dataset.py --seed 20261022 --scale starter --out-dir data/seed
python3 generator/validate_dataset.py --data-dir data/seed --seed 20261022 --scale starter
```
*(Optional: To generate the full 1,000,000-reading dataset locally on your laptop, run `python3 generator/generate_dataset.py --seed 20261022 --scale full --out-dir data/full_scale` — note that GitHub has a 100MB file size limit, so keep `data/full_scale` out of git using the included `.gitignore`, while `data/seed/full_scale_manifest.json` and `data/seed/full_scale_validation_summary.json` are already committed as verified proof!)*

### 1B. Start the Spring Boot (Java 25) Backend & Run JUnit Tests
```bash
cd backend
mvn test
mvn spring-boot:run
```
- The Spring Boot backend will start at **`http://localhost:8080`**.
- Test the API in your browser: `http://localhost:8080/api/overview` and `http://localhost:8080/api/exceptions/evaluate`.

### 1C. Start the ReactJS Frontend
Open a second terminal window:
```bash
cd frontend
npm install
npm run dev
```
- Open **`http://localhost:5173`** in your browser.
- Click **"Sync Spring Boot (:8080)"** in the top-right header to connect the React UI live to your local Spring Boot server!

---

## Step 2: Push the Complete Project to a Public GitHub Repository

1. Go to [https://github.com/new](https://github.com/new) and create a new **Public** repository named:
   `yottaflex-warehouse-telemetry` (do **not** check "Add a README" so the repo starts empty).
2. In your terminal, from the root of the extracted `yottaflex-warehouse-telemetry` folder, run:

```bash
git init
git add .
git commit -m "Feat: Complete YottaFlex.ai 72h Challenge (Spring Boot + ReactJS + Seed 20261022 Generator)"
git branch -M main
git remote add origin https://github.com/<YOUR_GITHUB_USERNAME>/yottaflex-warehouse-telemetry.git
git push -u origin main
```

Your **Public GitHub Repository URL** to submit on the YottaFlex.ai portal is:
`https://github.com/<YOUR_GITHUB_USERNAME>/yottaflex-warehouse-telemetry`

---

## Step 3: Get a Free Live Working URL in 60 Seconds (Vercel / Netlify / Render)

Because the ReactJS frontend (`frontend/`) includes the embedded deterministic `seed=20261022` engine as an automatic fallback when `localhost:8080` is not present, you can deploy a **24/7 live interactive URL** in under 60 seconds:

### Option A: Deploy Live via Vercel (Recommended — 60 Seconds)
1. Go to [https://vercel.com/new](https://vercel.com/new) and sign in with your GitHub account.
2. Click **Import** next to your `yottaflex-warehouse-telemetry` repository.
3. Set **Root Directory** to `frontend`.
4. Framework Preset will auto-detect **Vite**. Click **Deploy**.
5. In ~45 seconds, Vercel will give you a live public link such as:
   `https://yottaflex-warehouse-telemetry.vercel.app`
6. Add that live link to the top of your `README.md` (or share it alongside your GitHub repo link)!

### Option B: Run Full-Stack with Docker Compose
If reviewers want to spin up both the Spring Boot backend and React frontend with one command, `docker-compose.yml` is included at the root:
```bash
docker compose up --build
```
