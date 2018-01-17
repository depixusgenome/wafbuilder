if length(ARGS) > 0
    map(ARGS) do fname
        str = readstring(fname);
        if length(str) > 0
            socket = connect(2223);
            println(socket, fname);
            println(socket, length(str));
            println(socket, str);

            resp = false
            while isopen(socket)
                line = readline(socket)
                if length(line) > 1
                    println(line)
                    resp = true
                end
            end
            if resp
                error("Found errors in $fname")
            end
        end
    end
else
    try
        close(connect(2223))
    catch
        using Lint
        lintserver(2223)
    end
end
