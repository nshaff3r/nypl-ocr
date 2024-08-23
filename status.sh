#!/bin/bash

while true; do
    read_lines=$(wc -l < read.txt)
    unread_lines=$(wc -l < unread.txt)
    
    echo "read.txt: $read_lines, unread.txt: $unread_lines, total: $(( $read_lines + $unread_lines ))"
    
    sleep 1
done
