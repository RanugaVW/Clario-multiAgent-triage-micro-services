# WebXpay gateway and checkout discrepancies

WebXpay (the course-payment gateway) and the checkout flow around it can fail or disagree
with the dashboard in several distinct ways: a one-time password never arrives, an overseas
or split-card payment gets blocked or partially declined, a duplicate-enrollment check blocks
a legitimate second purchase, or the price actually charged doesn't match what a promo code,
referral link, reward points, or a flash-sale banner showed moments earlier. None of these
should be diagnosed as fraud or dismissed as customer error - acknowledge the specific
mismatch, confirm the transaction reference and amount actually charged, and explain that
payment-gateway discrepancies are verified against WebXpay's own transaction record before
anything is corrected, adjusted, or refunded. Do not confirm a transaction succeeded, promise
a price adjustment, or promise a specific refund amount before that verification happens.

**Common ways customers describe this:** didn't receive the OTP required to complete the WebXpay payment so the transaction couldn't be finished; paid via mobile banking app and got a success message but the LMS still shows the course as unpaid; payment from an overseas card is being blocked, seemingly due to an international transaction restriction; tried to split payment across two cards, one succeeded and one was declined, and is unsure if fully enrolled; already an enrolled student trying to buy a second course but checkout throws a duplicate-email error and won't allow payment; paid the flash-sale price shown on the landing page but was charged the regular full price at checkout; used a special discounted price from a referral link but the discount wasn't honored at checkout; the WebXpay transaction ID received doesn't match the one shown on the dashboard; tried to use a discount or promo code at checkout but it wasn't applied and was charged full price; added the course to cart at one price but was charged a higher amount at final payment; had reward points or wallet balance from a previous promotion that wasn't applied automatically at checkout.
