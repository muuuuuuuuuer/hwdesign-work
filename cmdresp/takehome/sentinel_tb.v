`timescale 1ns/1ps
module sentinel_tb;
  reg clk = 0, rst_n = 0;
  always #5 clk = ~clk;
  reg [31:0] in_data = 0;
  reg in_valid = 0, in_last = 0;
  wire in_ready;
  wire [31:0] out_data;
  wire out_valid, out_last;
  wire [3:0] out_keep, out_strb;
  reg awvalid=0, wvalid=0, arvalid=0, rready=0, bready=1;
  reg [5:0] awaddr=0, araddr=0;
  reg [31:0] wdata=0;
  wire awready, wready, arready, rvalid, bvalid, interrupt;
  wire [31:0] rdata;
  wire [1:0] rresp, bresp;

  fir4 dut(.ap_clk(clk), .ap_rst_n(rst_n),
    .in_stream_TDATA(in_data), .in_stream_TVALID(in_valid), .in_stream_TREADY(in_ready),
    .in_stream_TKEEP(4'hf), .in_stream_TSTRB(4'hf), .in_stream_TLAST(in_last),
    .out_stream_TDATA(out_data), .out_stream_TVALID(out_valid), .out_stream_TREADY(1'b1),
    .out_stream_TKEEP(out_keep), .out_stream_TSTRB(out_strb), .out_stream_TLAST(out_last),
    .s_axi_control_AWVALID(awvalid), .s_axi_control_AWREADY(awready), .s_axi_control_AWADDR(awaddr),
    .s_axi_control_WVALID(wvalid), .s_axi_control_WREADY(wready), .s_axi_control_WDATA(wdata),
    .s_axi_control_WSTRB(4'hf), .s_axi_control_ARVALID(arvalid), .s_axi_control_ARREADY(arready),
    .s_axi_control_ARADDR(araddr), .s_axi_control_RVALID(rvalid), .s_axi_control_RREADY(rready),
    .s_axi_control_RDATA(rdata), .s_axi_control_RRESP(rresp), .s_axi_control_BVALID(bvalid),
    .s_axi_control_BREADY(bready), .s_axi_control_BRESP(bresp), .interrupt(interrupt));

  task start_kernel;
    begin
      @(negedge clk); awaddr=0; awvalid=1;
      do @(posedge clk); while (!awready);
      @(negedge clk); awvalid=0; wdata=1; wvalid=1;
      do @(posedge clk); while (!wready);
      @(negedge clk); wvalid=0;
      do @(posedge clk); while (!bvalid);
    end
  endtask

  task read_reg(input [5:0] addr, output reg [31:0] value);
    begin
      @(negedge clk); araddr=addr; arvalid=1;
      do @(posedge clk); while (!arready);
      @(negedge clk); arvalid=0; rready=1;
      do @(posedge clk); while (!rvalid);
      value = rdata;
      @(negedge clk); rready=0;
    end
  endtask

  integer fd, total, ci, n, i, code, tx, last, rc, fails, sent, presented;
  reg [31:0] word, status_halted, status_error, status_tx;
  reg [255:0] name;
  initial begin
    fd=$fopen("sentinel_vectors.txt", "r");
    if (!fd) $fatal(1, "Cannot open sentinel vectors");
    rc=$fscanf(fd, "%d\n", total); fails=0;
    for (ci=0; ci<total; ci=ci+1) begin
      rc=$fscanf(fd, "%s %d %d %d\n", name, n, code, tx);
      @(negedge clk); rst_n=0; in_valid=0;
      repeat (5) @(posedge clk);
      @(negedge clk); rst_n=1;
      repeat (5) @(posedge clk);
      start_kernel();
      for (i=0; i<n; i=i+1) begin
        rc=$fscanf(fd, "%h %d\n", word, last);
        @(negedge clk); in_data=word; in_last=last; in_valid=1;
        do @(posedge clk); while (!in_ready);
      end
      @(negedge clk); in_data=32'h7edcba98; in_last=1; in_valid=1; sent=0; presented=0;
      while (!dut.ap_done) begin
        @(posedge clk);
        if (in_valid) presented=presented+1;
        if (in_valid && in_ready) sent=sent+1;
        #1;
      end
      @(negedge clk); in_valid=0;
      read_reg(6'h10, status_halted);
      read_reg(6'h20, status_error);
      read_reg(6'h30, status_tx);
      if (presented == 0 || sent != 0 || status_halted != 1 || status_error != code || status_tx != tx) begin
        $display("SENTINEL FAIL %0s presented_cycles=%0d accepted=%0d status=(%0d,%0d,%0d) expected=(1,%0d,%0d)", name, presented, sent, status_halted, status_error, status_tx, code, tx);
        fails=fails+1;
      end else
        $display("SENTINEL PASS %0s presented_cycles=%0d accepted=%0d status=(%0d,%0d,%0d)", name, presented, sent, status_halted, status_error, status_tx);
    end
    $display("SENTINEL SUMMARY cases=%0d failed=%0d", total, fails);
    if (fails) $fatal(1, "RTL sentinel tests failed");
    $finish;
  end
  initial begin #10000000; $fatal(1, "RTL sentinel test timeout"); end
endmodule
