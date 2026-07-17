/* OneSignal push notification worker for Stacks.
   Runs in its own scope (/onesignal/) so it never
   conflicts with the site's offline worker (sw.js). */
importScripts("https://cdn.onesignal.com/sdks/web/v16/OneSignalSDK.sw.js");
