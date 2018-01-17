function lintone(fname::AbstractString, str::AbstractString, doprint::Bool)
    if length(str) == 0
        return
    end

    socket = connect(2223)
    println(socket, fname);
    println(socket, length(str));
    println(socket, str);

    resp = false
    while isopen(socket)
        line = readline(socket)
        if length(line) > 1 && doprint
            println(line)
            resp = true
        end
    end
    if resp && doprint
        error("Found errors in $fname")
    end
end

uselint = false
try
    lintone("nothing", "1+1", false)
catch
    using Lint
    uselint = true
end

if length(ARGS) == 0
    if uselint == false
        lintserver(2223)
    end
else
    map(uselint ? lintfile : x->lintone(x, readstring(x), true), ARGS)
end
