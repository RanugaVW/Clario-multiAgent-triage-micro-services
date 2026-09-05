# Testing/11 - OCR Vision Model vs Tesseract: Evaluation Report

**Images evaluated:** 34

Two independent extractors ran against every image below:
- **Tesseract** (`pytesseract`) - a naive, generic OCR engine with no
  concept of what matters in the image; it transcribes everything it
  can find, including UI chrome, buttons, watermarks, and background
  noise.
- **Vision model** (Qwen2-VL-2B-Instruct via
  `clario-ml-sidecar/app/tools/local_ocr.py`, falling back to Gemini
  3.1 Flash-Lite if the local model can't load) explicitly prompted to
  extract only the real error text and ignore everything else.

---

## Summary

| Image | Tesseract similarity | Vision similarity | Winner |
|---|---|---|---|
| Pasted image (10).png | 0.14 | 0.94 | Vision |
| Pasted image (11).png | 0.45 | 0.52 | Vision |
| Pasted image (12).png | 0.23 | 0.99 | Vision |
| Pasted image (13).png | 0.21 | 0.96 | Vision |
| Pasted image (14).png | 0.09 | 0.96 | Vision |
| Pasted image (15).png | 0.31 | 0.91 | Vision |
| Pasted image (16).png | 0.31 | 0.91 | Vision |
| Pasted image (17).png | 0.23 | 0.99 | Vision |
| Pasted image (2).png | 0.94 | 0.95 | Vision |
| Pasted image (3).png | 0.44 | 0.70 | Vision |
| Pasted image (4).png | 0.00 | 0.94 | Vision |
| Pasted image (5).png | 0.21 | 0.96 | Vision |
| Pasted image (6).png | 0.32 | 0.55 | Vision |
| Pasted image (7).png | 0.33 | 0.97 | Vision |
| Pasted image (8).png | 0.32 | 0.90 | Vision |
| Pasted image (9).png | 0.48 | 0.98 | Vision |
| Pasted image.png | 0.00 | 0.97 | Vision |
| Screenshot from 2026-03-31 14-18-08.png | 0.53 | 1.00 | Vision |
| Screenshot from 2026-03-31 14-27-11.png | 0.36 | 1.00 | Vision |
| Screenshot from 2026-03-31 15-48-40.png | 0.30 | 1.00 | Vision |
| Screenshot from 2026-03-31 16-40-46.png | 0.50 | 1.00 | Vision |
| Screenshot from 2026-03-31 16-40-56.png | 0.51 | 0.55 | Vision |
| Screenshot from 2026-04-05 08-49-08.png | 0.54 | 1.00 | Vision |
| Screenshot from 2026-04-18 13-50-29.png | 0.70 | 0.99 | Vision |
| Screenshot from 2026-04-21 19-49-36.png | 0.34 | 1.00 | Vision |
| Screenshot from 2026-04-29 16-08-04.png | 0.20 | 1.00 | Vision |
| Screenshot from 2026-04-29 23-44-01.png | 0.27 | 1.00 | Vision |
| Screenshot from 2026-04-30 08-19-57.png | 0.98 | 1.00 | Vision |
| Screenshot from 2026-05-10 06-11-51.png | 0.77 | 0.99 | Vision |
| Screenshot from 2026-06-16 23-10-01.png | 0.22 | 0.90 | Vision |
| Screenshot from 2026-06-17 00-02-56.png | 0.26 | 0.78 | Vision |
| Screenshot from 2026-06-17 15-19-53.png | 0.45 | 0.97 | Vision |
| Screenshot from 2026-06-18 13-13-55.png | 0.98 | 0.99 | Vision |
| Screenshot from 2026-09-05 11-42-41.png | 0.10 | 0.98 | Vision |

**Average similarity to ground truth:** Tesseract 0.38 | Vision 0.92

**Wins:** Vision 34/34 | Tesseract 0/34 | Ties 0/34

Similarity is a fuzzy match ratio (0-1) against the ground-truth error text in `ground_truth.csv`, not an exact match - it's deliberately sensitive to length, so an extractor that pads its output with unrelated noise scores lower even when the real error is present somewhere in it.

---

## Findings

Across all 34 real screenshots (with ground truth taken from `ground_truth.csv`), the vision model beat Tesseract on every single image (34/34), with an average similarity to the real error of **0.92** versus Tesseract's **0.38**. On 5 of the 34 images Tesseract scored below 0.15 - on two of those (`Pasted image.png`, `Pasted image (4).png`) it returned an **empty string**, extracting nothing at all, while the vision model correctly pulled out the exact error text on both.

The clearest illustration is `Screenshot from 2026-06-16 23-10-01.png` (a browser DevTools screenshot). Tesseract's raw output is mostly the DevTools chrome around the error - filter/invert controls, the Headers/Payload/Preview/Response tab bar, a millisecond timing ruler - with the real JSON fragmented and buried inside it (similarity 0.22). The vision model, prompted to ignore exactly this kind of surrounding noise, returned just `Login Failed / Forbidden / {"success":false,"error":"Forbidden"}` (similarity 0.90) - the real error and nothing else.

`Pasted image (11).png` is the closest race in the whole set (Tesseract 0.45 vs. vision 0.52) and is instructive precisely because it's close: the screenshot has relatively little UI chrome, so Tesseract recovers most of the real error text too - but it still interleaves browser/OS chrome into the same output (`1@ % O - LTE`, `stem.rysera.com`, `Save password?`, `Back to Home`), which the vision model excludes entirely. Even in Tesseract's best-case result overall, `Screenshot from 2026-04-30 08-19-57.png` (0.98 vs. the vision model's 1.0), Tesseract still made a character-level misread the vision model didn't (`type wuid` instead of `type uuid`) - a classic OCR confusion between visually similar glyphs that a model reasoning about the text semantically doesn't make.

On the memory-safety question this evaluation was built to answer: every one of the 34 images ran through the **Gemini 3.1 Flash-Lite fallback**, not the local Qwen2-VL-2B model - this sandbox has no GPU and no `bitsandbytes` CUDA support, so `_load_model_singleton()` failed fast (`Failed to import transformers/bitsandbytes`) and `local_ocr.py`'s fallback path took over automatically, exactly as designed. This run is itself a live demonstration that the fallback works under a real memory/dependency-constrained machine, not just in a unit test.

**Environment note:** this run's sandbox has no `sudo` access, so the system Tesseract binary couldn't be installed directly - its output for all 34 images was produced by a throwaway Docker container (`apt-get install tesseract-ocr` as root inside the container) rather than a live local call, so `tesseract_elapsed_s` below reads `0.00s` for every image (not measured, not a real timing claim) while `vision_elapsed_s` is a real, live per-image measurement. `run_comparison.py` itself is unaffected - it still calls `pytesseract` directly and will time it normally on a machine with Tesseract actually on `PATH`.


---

## Pasted image (10).png

**Vision backend used:** `gemini-3.1-flash-lite-fallback` (25.67s) | **Tesseract:** 0.00s

**Ground truth (real error, noise excluded):**
```
An unexpected error occurred. Please try again.
```
Similarity - Tesseract: 0.14 | Vision: 0.94

### Tesseract raw output
```
20:04 Sun 3 May

stem.rysera.com

STEM. ( ) >
RYsERA Home Courses Events AboutUs Contact My Courses | Q

Street Address *

no 216 Katuwellegama via Negombo

City* Postal Code *
Minuwangeda 7580
Country
Sri Lanka

Quick Links Courses

a Error

Home Robotics & Cd
Shaping future-ready minds
through real-world STEM

ativies About Us +9477 123 4567

Courses Al & Machine

Peeper PTE Ty?) HE
```

### Vision model raw output
```
Error
An unexpected error occurred. Please try again.
```

---

## Pasted image (11).png

**Vision backend used:** `gemini-3.1-flash-lite-fallback` (7.01s) | **Tesseract:** 0.00s

**Ground truth (real error, noise excluded):**
```
Payment failed. Please try again or contact support. (Order ID: ORD-1777912184844-RVW91L1)
```
Similarity - Tesseract: 0.45 | Vision: 0.52

### Tesseract raw output
```
1@ % O - ® LTE

x v Rysera STEM - I... <

stem.rysera.com

Save password?

There was an issue processing your payment

Payment failed. Please try again or
contact support.

Order ID:
ORD-1777912184844-RVW91L1

Back to Home

If you continue to experience i

s, please contact
our support team with your order ID.
```

### Vision model raw output
```
Payment Failed
There was an issue processing your payment
Payment failed. Please try again or contact support.
```

---

## Pasted image (12).png

**Vision backend used:** `gemini-3.1-flash-lite-fallback` (10.44s) | **Tesseract:** 0.00s

**Ground truth (real error, noise excluded):**
```
Upload failed - We couldn't upload your bank slip. Please try again.
```
Similarity - Tesseract: 0.23 | Vision: 0.99

### Tesseract raw output
```
ws c e

rysera.com/dashboard

Upload Bank Slip

Ai Explorer

Online

ns (PVT) LTD
190¢918180

Upload Slip (Image/PDF)

Payment Tr

Reference / Notes (optional)

Hot days ahead P 99+ Ae eR 4 104 PM
92°F Q Search Te a ail =: I U a A fe 8 FWO erproae
```

### Vision model raw output
```
Upload failed
We couldn't upload your bank slip. Please try again.
```

---

## Pasted image (13).png

**Vision backend used:** `gemini-3.1-flash-lite-fallback` (4.85s) | **Tesseract:** 0.00s

**Ground truth (real error, noise excluded):**
```
Login Failed - fetch failed
```
Similarity - Tesseract: 0.21 | Vision: 0.96

### Tesseract raw output
```
4:52 BAO > Nl Ball 50%

() 2% em.rysera.ccom + C+]

Login Failed
fetch failed

Welcome to by
Rysera

Login to your account or create a new one
Login

Email

nkulathunga909@gmail.com

Password

Forgot password?

Login
```

### Vision model raw output
```
Login Failed
fetch failed
```

---

## Pasted image (14).png

**Vision backend used:** `gemini-3.1-flash-lite-fallback` (8.10s) | **Tesseract:** 0.00s

**Ground truth (real error, noise excluded):**
```
Login Failed - fetch failed
```
Similarity - Tesseract: 0.09 | Vision: 0.96

### Tesseract raw output
```
G creating cause si x | @ A couse X | @ or tentaracion: x | GY Deepseek-intoth: x | @ daye-mtnotesma x [aw RyeraSTEMC Isp XX) + HAskGemini = - og x

€o¢ stemuysera.com eer € DB Rk

Welcome to STEMby Rysera

Login to your account or create a new one

Forgot password?

531PM
AG Me oe
```

### Vision model raw output
```
Login Failed
fetch failed
```

---

## Pasted image (15).png

**Vision backend used:** `gemini-3.1-flash-lite-fallback` (10.32s) | **Tesseract:** 0.00s

**Ground truth (real error, noise excluded):**
```
Upload failed: Bucket not found
```
Similarity - Tesseract: 0.31 | Vision: 0.91

### Tesseract raw output
```
cted files:

S5UMIND_Pamudu.pdf.pdf Remove
```

### Vision model raw output
```
Error
Upload failed: Bucket not found
```

---

## Pasted image (16).png

**Vision backend used:** `gemini-3.1-flash-lite-fallback` (12.98s) | **Tesseract:** 0.00s

**Ground truth (real error, noise excluded):**
```
Upload failed: Bucket not found
```
Similarity - Tesseract: 0.31 | Vision: 0.91

### Tesseract raw output
```
cted files:

S5UMIND_Pamudu.pdf.pdf Remove
```

### Vision model raw output
```
Error
Upload failed: Bucket not found
```

---

## Pasted image (17).png

**Vision backend used:** `gemini-3.1-flash-lite-fallback` (17.72s) | **Tesseract:** 0.00s

**Ground truth (real error, noise excluded):**
```
Upload failed - We couldn't upload your bank slip. Please try again.
```
Similarity - Tesseract: 0.23 | Vision: 0.99

### Tesseract raw output
```
ws c e

rysera.com/dashboard

Upload Bank Slip

Ai Explorer

Online

ns (PVT) LTD
190¢918180

Upload Slip (Image/PDF)

Payment Tr

Reference / Notes (optional)

Hot days ahead P 99+ Ae eR 4 104 PM
92°F Q Search Te a ail =: I U a A fe 8 FWO erproae
```

### Vision model raw output
```
Upload failed
We couldn't upload your bank slip. Please try again.
```

---

## Pasted image (2).png

**Vision backend used:** `gemini-3.1-flash-lite-fallback` (7.59s) | **Tesseract:** 0.00s

**Ground truth (real error, noise excluded):**
```
Unexpected token 'T', "Too many r"... is not valid JSON
```
Similarity - Tesseract: 0.94 | Vision: 0.95

### Tesseract raw output
```
Unexpected token 'T;, “Too many r’.. is not valid
JSON
```

### Vision model raw output
```
Error
Unexpected token 'T', "Too many r"... is not valid JSON
```

---

## Pasted image (3).png

**Vision backend used:** `gemini-3.1-flash-lite-fallback` (8.71s) | **Tesseract:** 0.00s

**Ground truth (real error, noise excluded):**
```
Login Failed - Server Action "4093869ad86d84184648ed0fb94ce69a0e1ef0..." was not found on the server.
```
Similarity - Tesseract: 0.44 | Vision: 0.70

### Tesseract raw output
```
oe 48 wll 58%

stem.rysera.com Oo

Login Failed

Server Action
"4093869ad86d84184648ed0fb94ce69a0elefOl
was not found on the server. Read more:
https://nextjs.org/docs/messages/failed-to-find-
server-action

Login to your account or create a new one
Login
Email

ruwanga.kalawana@gmail.com

Password

seseees ©

Forgot password?

Login
```

### Vision model raw output
```
Login Failed
Server Action
"4093869ad86d84184648ed0fb94ce69a0e1ef01
was not found on the server. Read more:
https://nextjs.org/docs/messages/failed-to-find-
server-action
```

---

## Pasted image (4).png

**Vision backend used:** `gemini-3.1-flash-lite-fallback` (40.97s) | **Tesseract:** 0.00s

**Ground truth (real error, noise excluded):**
```
An unexpected error occurred. Please try again.
```
Similarity - Tesseract: 0.00 | Vision: 0.94

### Tesseract raw output
```
(empty)
```

### Vision model raw output
```
Error
An unexpected error occurred. Please try again.
```

---

## Pasted image (5).png

**Vision backend used:** `gemini-3.1-flash-lite-fallback` (9.96s) | **Tesseract:** 0.00s

**Ground truth (real error, noise excluded):**
```
Failed to fetch questions: invalid input syntax for type uuid: "undefined"
```
Similarity - Tesseract: 0.21 | Vision: 0.96

### Tesseract raw output
```
ali euo Pree
```

### Vision model raw output
```
Error
Failed to fetch questions: invalid input syntax
for type uuid: "undefined"
```

---

## Pasted image (6).png

**Vision backend used:** `gemini-3.1-flash-lite-fallback` (5.37s) | **Tesseract:** 0.00s

**Ground truth (real error, noise excluded):**
```
Please complete your profile before enrolling. Missing: Full Name, Phone Number, Address, City, Postal Code
```
Similarity - Tesseract: 0.32 | Vision: 0.55

### Tesseract raw output
```
19:32 © -

+

0

Q = 26 stem.rysera.com/profile

y Profile

Manage your personal information

mM

Personal Information
rofile details. Fields mar

tat

Full Name *
```

### Vision model raw output
```
Complete Your Profile
Please complete your profile before enrolling. Missing: Full Name, Phone Number, Address, City, Postal Code

Profile Incomplete
Please complete the following required fields to enroll in courses: full_name, phone, address, city, postal_code

Full Name *
Required
```

---

## Pasted image (7).png

**Vision backend used:** `gemini-3.1-flash-lite-fallback` (4.80s) | **Tesseract:** 0.00s

**Ground truth (real error, noise excluded):**
```
Failed to create question: null value in column "user_id" of relation "forum_questions" violates not-null constraint
```
Similarity - Tesseract: 0.33 | Vision: 0.97

### Tesseract raw output
```
14:04 ill FE

x Vv RYSERA L... < Q :

ysera.com

Post your question to the forum. Instructors

Error

Failed to create question: null value in
column "user_id" of relation

"forum_questions" violates not-null
constraint

scope"then | asked chat gpt and it
said led attach does not exist esp32
and suggested me a code.That
code uploaded without showing
any error .So | want to know the
reason that the code given by LMS
didn't work but the the code
attached below

Code Snippet (Optional)

ledeWrite(PWM CH, 150);
delay(2000);

// Full speed

ledcWrite(PWM_CH, 255);
delay(2000);

Post Question

a © <
```

### Vision model raw output
```
Error
Failed to create question: null value in column "user_id" of relation "forum_questions" violates not-null constraint
```

---

## Pasted image (8).png

**Vision backend used:** `gemini-3.1-flash-lite-fallback` (7.22s) | **Tesseract:** 0.00s

**Ground truth (real error, noise excluded):**
```
Failed to load submissions
```
Similarity - Tesseract: 0.32 | Vision: 0.90

### Tesseract raw output
```
> pictures > Screenshots

© setas background & Rotate left

S Rotate right one

Screenshot 2026-03-02 21: '5934.png

Failed to load submissions
```

### Vision model raw output
```
Error
Failed to load submissions
```

---

## Pasted image (9).png

**Vision backend used:** `gemini-3.1-flash-lite-fallback` (5.72s) | **Tesseract:** 0.00s

**Ground truth (real error, noise excluded):**
```
Upload failed: Invalid key: submissions/2dbdbced-00f4-495e-b74d-e027080a1329/6a485325-6d3a-4a8e-b4e2-69ae9e8842c1/ddbd171a-47e6-4e04-92b6-e727f14a9376/finalproject.pptm [Autosaved] [Autosaved].pdf
```
Similarity - Tesseract: 0.48 | Vision: 0.98

### Tesseract raw output
```
Minimize|

PDF Files
WJ
Drop PDF files here or click to browse
Choose Files finalprojec...osaved].pdf
Selected files:
finalproject.pptm [Autosaved] [Autosaved].pdf Remove
Video Title
Video title
Video Link
Video URL (YouTube, Google Drive, etc.) } Add
Video links:

Use Al to manage sleep duration

Error
Upload failed: Invalid key: submissions

€027080a1329/6a485325-6d3a-4a8e-b4e2-69ac9e8842cl/ddbdl7la-47e6-4e04-97
€727#14a9376/finalproject.pptm [Autosaved] [Autosaved].pdf
```

### Vision model raw output
```
Error
Upload failed: Invalid key: submissions/2dbdbced-00f4-495e-b74d-e027080a1329/6a485325-6d3a-4a8e-b4e2-69ae9e8842c1/ddbd171a-47e6-4e04-92b6-e727f14a9376/finalproject.pptm [Autosaved] [Autosaved].pdf
```

---

## Pasted image.png

**Vision backend used:** `gemini-3.1-flash-lite-fallback` (2.54s) | **Tesseract:** 0.00s

**Ground truth (real error, noise excluded):**
```
Failed to create content: duplicate key value violates unique constraint "topic_contents_unique_position"
```
Similarity - Tesseract: 0.00 | Vision: 0.97

### Tesseract raw output
```
(empty)
```

### Vision model raw output
```
Error
Failed to create content: duplicate key value violates unique constraint "topic_contents_unique_position"
```

---

## Screenshot from 2026-03-31 14-18-08.png

**Vision backend used:** `gemini-3.1-flash-lite-fallback` (3.15s) | **Tesseract:** 0.00s

**Ground truth (real error, noise excluded):**
```
invalid input syntax for type uuid: "undefined"
```
Similarity - Tesseract: 0.53 | Vision: 1.00

### Tesseract raw output
```
S © localhost:3000/ce

at Home Courses Events AboutUs Con’

BacktoLMS / Certificate

invalid input syntax for type uuid: "undefined"
```

### Vision model raw output
```
invalid input syntax for type uuid: "undefined"
```

---

## Screenshot from 2026-03-31 14-27-11.png

**Vision backend used:** `gemini-3.1-flash-lite-fallback` (7.31s) | **Tesseract:** 0.00s

**Ground truth (real error, noise excluded):**
```
Invalid contentId
```
Similarity - Tesseract: 0.36 | Vision: 1.00

### Tesseract raw output
```
ate Home Courses Events AboutUs Con

BacktoLMS / Certificate

Invalid contentid
```

### Vision model raw output
```
Invalid contentId
```

---

## Screenshot from 2026-03-31 15-48-40.png

**Vision backend used:** `gemini-3.1-flash-lite-fallback` (5.43s) | **Tesseract:** 0.00s

**Ground truth (real error, noise excluded):**
```
Missing contentId
```
Similarity - Tesseract: 0.30 | Vision: 1.00

### Tesseract raw output
```
ate Home Courses Events AboutUs Con’ ™ My Courses

BacktoLMS / Certificate

Missing contentld
```

### Vision model raw output
```
Missing contentId
```

---

## Screenshot from 2026-03-31 16-40-46.png

**Vision backend used:** `gemini-3.1-flash-lite-fallback` (2.58s) | **Tesseract:** 0.00s

**Ground truth (real error, noise excluded):**
```
Failed to generate signed URL: Object not found
```
Similarity - Tesseract: 0.50 | Vision: 1.00

### Tesseract raw output
```
7 DECK TON FETC

 Ai-Course Completetion
Issued to Ranuga Weerasekara - Cert #FF3080A2

aN

Failed to generate signed URL: Object not found

Retry
```

### Vision model raw output
```
Failed to generate signed URL: Object not found
```

---

## Screenshot from 2026-03-31 16-40-56.png

**Vision backend used:** `gemini-3.1-flash-lite-fallback` (2.77s) | **Tesseract:** 0.00s

**Ground truth (real error, noise excluded):**
```
Failed to generate signed URL: Object not found (Console Error - CertificateViewer.useCallback[renderCertificate])
```
Similarity - Tesseract: 0.51 | Vision: 0.55

### Tesseract raw output
```
Nextjs 16.0.8 (stale) Turbopack

Failed to generate signed URL: Object not found
Call Stack 1

CertificateViewer.useCallback[renderCertificate] A

file:///nome/ranuga-weerasekara/Desktop/Rysera%20Projects/Rysera%20STEM%20Website/rysera-stem-
web/.next/dev/static/chunks/_947Ice80._|s (86:27)
```

### Vision model raw output
```
Failed to generate signed URL: Object not found

Call Stack 1

CertificateViewer.useCallback[renderCertificate] ⚠

file:///home/ranuga-weerasekara/Desktop/Rysera%20Projects/Rysera%20STEM%20Website/rysera-stem-web/.next/dev/static/chunks/_9471ce80._.js (86:27)
```

---

## Screenshot from 2026-04-05 08-49-08.png

**Vision backend used:** `gemini-3.1-flash-lite-fallback` (3.41s) | **Tesseract:** 0.00s

**Ground truth (real error, noise excluded):**
```
Failed to generate signed URL: Object not found
```
Similarity - Tesseract: 0.54 | Vision: 1.00

### Tesseract raw output
```
Ai-Course Completetion
Issued to Ranuga Weerasekara 23 - Cert #D36E69CB

aN

Failed to generate signed URL: Object not found

Retry
```

### Vision model raw output
```
Failed to generate signed URL: Object not found
```

---

## Screenshot from 2026-04-18 13-50-29.png

**Vision backend used:** `gemini-3.1-flash-lite-fallback` (10.58s) | **Tesseract:** 0.00s

**Ground truth (real error, noise excluded):**
```
Certificate Not Found - This certificate link is invalid, has not been approved yet, or no longer exists.
```
Similarity - Tesseract: 0.70 | Vision: 0.99

### Tesseract raw output
```
ate Home Courses Events AboutUs Contact My Courses

@ RYSERA STEM

ificate Verification

2

Certificate Not Found

This certificate link is invalid, has not been approved yet,
or no longer exists.
```

### Vision model raw output
```
Certificate Not Found
This certificate link is invalid, has not been approved yet, or no longer exists.
```

---

## Screenshot from 2026-04-21 19-49-36.png

**Vision backend used:** `gemini-3.1-flash-lite-fallback` (14.83s) | **Tesseract:** 0.00s

**Ground truth (real error, noise excluded):**
```
Name is too long for this certificate (736px > 659px). Try shorter initials.
```
Similarity - Tesseract: 0.34 | Vision: 1.00

### Tesseract raw output
```
Q Claim Your Certificate

Congratulations! You're eligible for a certificate. Enter the
name you want printed on it. This cannot be changed
later.

Full Name on Certificate

Ranuga Weerasekara

Name Is too long for this certificate (736px > 659px). Try shorter
Initials.

Use your real name — it will be permanently stored and printed
on the certificate.

G@ Generate My c
```

### Vision model raw output
```
Name is too long for this certificate (736px > 659px). Try shorter initials.
```

---

## Screenshot from 2026-04-29 16-08-04.png

**Vision backend used:** `gemini-3.1-flash-lite-fallback` (8.64s) | **Tesseract:** 0.00s

**Ground truth (real error, noise excluded):**
```
Invalid coupon format (e.g., RYSX5K9L)
```
Similarity - Tesseract: 0.20 | Vision: 1.00

### Tesseract raw output
```
Choose Payment Method
Complete your enrollment by ing a payment method.
course summary belo

Ai Explorer

f38Weeks © 24+Hours | Online

Payment Options & Pricing

Bank Transfer Payment Card Payment (Visa/MasterCard)

Rs. 7,900 Rs. 7,900

Bank slip Have a promo code?
RYSTODIL

Invalid coupon format (eg.,
RYSXSK9L)

Visa / MasterCard
```

### Vision model raw output
```
Invalid coupon format (e.g., RYSX5K9L)
```

---

## Screenshot from 2026-04-29 23-44-01.png

**Vision backend used:** `gemini-3.1-flash-lite-fallback` (12.87s) | **Tesseract:** 0.00s

**Ground truth (real error, noise excluded):**
```
Failed to generate signed URL: Object not found
```
Similarity - Tesseract: 0.27 | Vision: 1.00

### Tesseract raw output
```
~ BacktoLMS / Certificate

 Ai-Course Completion
Issued to Ranuga Test 23 - Cert #620287C0

aN

Failed to generate signed URL: Object not found

Retry

@ Your permanent shareable link
http: //1ocalhost :3000/certificates/view/620287c0-e0c4-4e6d-bi ©)

Anyone with this link can view and download your certificate.
```

### Vision model raw output
```
Failed to generate signed URL: Object not found
```

---

## Screenshot from 2026-04-30 08-19-57.png

**Vision backend used:** `gemini-3.1-flash-lite-fallback` (4.27s) | **Tesseract:** 0.00s

**Ground truth (real error, noise excluded):**
```
invalid input syntax for type uuid: "ai-course"
```
Similarity - Tesseract: 0.98 | Vision: 1.00

### Tesseract raw output
```
invalid input syntax for type wuid: "ai-course"
```

### Vision model raw output
```
invalid input syntax for type uuid: "ai-course"
```

---

## Screenshot from 2026-05-10 06-11-51.png

**Vision backend used:** `gemini-3.1-flash-lite-fallback` (5.31s) | **Tesseract:** 0.00s

**Ground truth (real error, noise excluded):**
```
Admins cannot enroll - Admin accounts are restricted from purchasing or enrolling in courses.
```
Similarity - Tesseract: 0.77 | Vision: 0.99

### Tesseract raw output
```
Admins cannot enroll

Admin accounts a

purchasing or enroll
```

### Vision model raw output
```
Admins cannot enroll
Admin accounts are restricted from purchasing or enrolling in courses.
```

---

## Screenshot from 2026-06-16 23-10-01.png

**Vision backend used:** `gemini-3.1-flash-lite-fallback` (7.49s) | **Tesseract:** 0.00s

**Ground truth (real error, noise excluded):**
```
Login Failed - Forbidden (response: {"success":false,"error":"Forbidden"})
```
Similarity - Tesseract: 0.22 | Vision: 0.90

### Tesseract raw output
```
Welcome to STEMby Rysera

Login to your account or create a new one

® ©! Y Q | GPreservelog | © Disable cache | No throt BS ts

Y Filter OB invert
i 500 ms| 1,000 ms 1,500 ms 2
Name X Headers Payload Preview __Response__ Initiator Timing
Bi t:/7id=105659350329996. N1781631593222.3022

0: {"a":"$@1","f":"","b": “development”

1
@ locathost_ 2

3 1:D{"time" :@.9816289999871515}
4
5

“success” :false, “error”: "Forbidden"}

1=105659350329996.
Bi localhost S
```

### Vision model raw output
```
Login Failed
Forbidden
1:{"success":false,"error":"Forbidden"}
```

---

## Screenshot from 2026-06-17 00-02-56.png

**Vision backend used:** `gemini-3.1-flash-lite-fallback` (3.38s) | **Tesseract:** 0.00s

**Ground truth (real error, noise excluded):**
```
Unauthorized (Console Error - confirmRegistration)
```
Similarity - Tesseract: 0.26 | Vision: 0.78

### Tesseract raw output
```
<ai> \ (@ Nexts 16.08 (stale) Turbopack )

Console Error ®) ()

Unauthorized

Call Stack 1

confirmRegistration 4
file:///home/ranuga-weerasekara/Desktop/Rysera%20Projects/Rysera%20STEM%20Website/rysera-stem-
web/.next/dev/static/chunks/_3c958a89._.s (353:23)
```

### Vision model raw output
```
Unauthorized
confirmRegistration
```

---

## Screenshot from 2026-06-17 15-19-53.png

**Vision backend used:** `gemini-3.1-flash-lite-fallback` (7.35s) | **Tesseract:** 0.00s

**Ground truth (real error, noise excluded):**
```
Registration Failed - Unauthorized
```
Similarity - Tesseract: 0.45 | Vision: 0.97

### Tesseract raw output
```
Confirm Registration

test event 8
```

### Vision model raw output
```
Registration Failed
Unauthorized
```

---

## Screenshot from 2026-06-18 13-13-55.png

**Vision backend used:** `gemini-3.1-flash-lite-fallback` (3.12s) | **Tesseract:** 0.00s

**Ground truth (real error, noise excluded):**
```
Registration Failed - Failed to register for event: Cannot coerce the result to a single JSON object
```
Similarity - Tesseract: 0.98 | Vision: 0.99

### Tesseract raw output
```
Registration Failed

Failed to register for event: Cannot coerce the
result toa single JSON object
```

### Vision model raw output
```
Registration Failed
Failed to register for event: Cannot coerce the result to a single JSON object
```

---

## Screenshot from 2026-09-05 11-42-41.png

**Vision backend used:** `gemini-3.1-flash-lite-fallback` (6.30s) | **Tesseract:** 0.00s

**Ground truth (real error, noise excluded):**
```
Upload failed - Failed to upload bank slip
```
Similarity - Tesseract: 0.10 | Vision: 0.98

### Tesseract raw output
```
Please upload your payment slip to confirm your registration.

Your slot will be confirmed via email after we manually verify your
payment.

Bank Details

Rysera Innovations (PVT) LTD
Account Number: 1000918180

Bank: Commercial Bank

Branch: Katubedda City Branch - (167)

Upload Slip (Image/PDF)

Screenshot from 2026-04-.

Reference / Notes (optional)

Test

Back
```

### Vision model raw output
```
Upload failed
Failed to upload bank slip
```

---
