DIE BOT DIE
---


A simple Twitter bot that searches a variety of topics for active users, 
examines them for troll/bot like traits and then blocks them.

Redis isn't strictly necessary. fakeredis would likely work just
as well for this purpose but a real redis does allow for resuming if
execution is stopped. File size so far has been only a few megabytes.

Die Bot Die collects topics from:
1. Current Twitter trends in the United States
2. Trending hashtags & keywords from [Hamilton 68](https://dashboard.securingdemocracy.org/),
    a site that tracks propaganda by Russian influencers
3. Replies to accounts followed by the credentials' user

One topic at a time, it does a search for the most recent 100 tweets,
storing the most recent id in redis for future searches. If an account
has any of:
1. 8 digits at the end of the username
2. Default profile picture
3. One of the provided name keywords in the screen name
4. One of the provided profile keywords in the profile
5. Profile or screen names with excessive number of emojis

the account is blocked. If a user doesn't violate any of these tenets,
they're marked as clean and not checked again.

(I initially planned to also pull in followers of blocked accounts &
 check them but the rate limit for that endpoint is very low.)

This can be run on your own account and/or shared with
[blocktogether](https://www.blocktogether.org). 
blocktogether has a limit of 250,000 blocks. I don't know if that
applies to Twitter as well but I suspect I will be finding out by the
end of the week. It blocked 50,000 in the first few days.

The twitter client is very simple & basic and will automatically wait
out the remaining time in a rate limit window. The script is currently
written to space out searches so it doesn't hit the limit.
