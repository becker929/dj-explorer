g2022-02-11

The flask server runs! 

![The flask server runs!](/static/1.png)

2022-02-11

Serious issues with managing dependencies, though. 

`pyenv` was taking for**eve**r to get working — turns out I was using `bash` instead of `zsh`, even though my integrated VS Code shell seemed to be telling me it was using `zsh`.

I traced it to this package `soundscrape`, but I'm not sure if I actually need that or not.

![I traced it to this package `soundscrape`](/static/2.png)

Seems `soundcloud` is also relying on `fudge`.

Still getting `The WebSocket transport is not available, you must install a WebSocket server that is compatible with your async mode to enable it. See the documentation for details.`

I've gotta get my dev environment to be repeatable... for instance not being able to scroll up in terminal practically forever is super annoying.


11pm

At this point I've formatted my code, sorted my imports, cursed the packaged I'd hoped would give me the correct requirements, frozen my requirements, and have everything working except the darn WebSockets!

I want to go back to earlier commits and try to get the project working from that state.

I'm starting to think I might want to start a clean repo and produce a sequence of atomic commits,... not sure. I'd prefer to use "prior art".

Also, I deleted my beautiful screenshots above because I didn't realize `git rm` would actually delete files when the `--cached` flag wasn't used.

